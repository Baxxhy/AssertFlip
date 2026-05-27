import ast
import difflib
import re
from pathlib import Path
from typing import Any

from .io import resolve_repo_file


CONTROL_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith)


def _line_relevance(line: str, problem_statement: str, patch: str) -> int:
    text = f"{problem_statement}\n{patch}".lower()
    words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text))
    line_words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", line.lower())
    return sum(1 for word in line_words if word in words)


def choose_target_location(dataset: dict[str, Any]) -> dict[str, Any]:
    localization = dataset.get("line_level_localization") or []
    localized_code = dataset.get("localized_code") or ""
    problem_statement = dataset.get("problem_statement") or ""
    patch = dataset.get("patch") or dataset.get("test_patch") or ""

    if localization:
        entry = localization[0]
        filename = entry.get("filename", "")
        suspect_lines = entry.get("suspect_lines") or entry.get("lines") or []
        patch_line = _patch_line_for_file(patch, filename, set(int(x) for x in suspect_lines if str(x).isdigit()))
        if patch_line:
            return {"file": filename, "line": patch_line, "selection_reason": "patch line intersecting suspicious lines"}
        if suspect_lines:
            useful_line = _first_useful_suspicious_line(localized_code, filename, suspect_lines)
            return {"file": filename, "line": useful_line, "selection_reason": "top useful suspicious line"}
        if entry.get("line"):
            return {"file": filename, "line": int(entry["line"]), "selection_reason": "localized line"}

    blocks = re.split(r"\n(?=### )", localized_code)
    best = {"file": "", "line": 0, "score": -1, "selection_reason": "localized code relevance"}
    for block in blocks:
        header = re.match(r"###\s+(.+)", block.strip())
        if not header:
            continue
        filename = header.group(1).strip()
        for raw_line in block.splitlines():
            match = re.match(r"\s*(\d+)\|\s?(.*)", raw_line)
            if not match:
                continue
            score = _line_relevance(match.group(2), problem_statement, patch)
            if score > best["score"]:
                best = {"file": filename, "line": int(match.group(1)), "score": score, "selection_reason": "localized code relevance"}
    return best


def _patch_line_for_file(patch: str, filename: str, suspect_lines: set[int]) -> int | None:
    if not patch or not filename:
        return None
    active = False
    old_line = None
    for raw in patch.splitlines():
        if raw.startswith("diff --git "):
            active = f" b/{filename}" in raw or raw.endswith(f" {filename}")
            continue
        if not active:
            continue
        hunk = re.match(r"@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@", raw)
        if hunk:
            old_line = int(hunk.group(1))
            continue
        if old_line is None:
            continue
        if raw.startswith("-") and not raw.startswith("---"):
            if old_line in suspect_lines:
                return old_line
            old_line += 1
        elif raw.startswith("+") and not raw.startswith("+++"):
            continue
        else:
            old_line += 1
    return None


def _first_useful_suspicious_line(localized_code: str, filename: str, suspect_lines: list[Any]) -> int:
    suspect_ints = [int(x) for x in suspect_lines if str(x).isdigit()]
    for line in suspect_ints:
        statement = _extract_localized_statement(localized_code, filename, line).strip()
        if statement and not statement.startswith("#") and statement not in {'"""', "'''"}:
            return line
    return suspect_ints[0]


class _ParentAnnotator(ast.NodeVisitor):
    def visit(self, node: ast.AST) -> Any:
        for child in ast.iter_child_nodes(node):
            setattr(child, "_parent", node)
        return super().visit(node)


def _node_contains_line(node: ast.AST, line: int) -> bool:
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", start)
    return start is not None and start <= line <= (end or start)


def _nearest_statement(tree: ast.AST, line: int) -> ast.AST | None:
    candidates = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.stmt) and _node_contains_line(node, line)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda n: getattr(n, "lineno", 0))


def _enclosing_function(tree: ast.AST, line: int) -> ast.AST | None:
    funcs = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _node_contains_line(node, line)
    ]
    if not funcs:
        return None
    return max(funcs, key=lambda n: getattr(n, "lineno", 0))


def _guard_conditions(source: str, stmt: ast.AST | None) -> list[str]:
    guards = []
    node = stmt
    while node is not None:
        parent = getattr(node, "_parent", None)
        if isinstance(parent, ast.If):
            text = ast.get_source_segment(source, parent.test) or ast.unparse(parent.test)
            guards.append(f"if {text}")
        elif isinstance(parent, ast.While):
            text = ast.get_source_segment(source, parent.test) or ast.unparse(parent.test)
            guards.append(f"while {text}")
        elif isinstance(parent, (ast.For, ast.AsyncFor)):
            text = ast.get_source_segment(source, parent.iter) or ast.unparse(parent.iter)
            guards.append(f"for ... in {text}")
        elif isinstance(parent, ast.Try):
            guards.append("inside try/except/finally block")
        node = parent
    return list(reversed(guards))


def _loaded_names(node: ast.AST | None) -> list[str]:
    if node is None:
        return []
    names = sorted({n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)})
    return names


def _defined_names_before(func: ast.AST | None, line: int) -> dict[str, list[int]]:
    definitions: dict[str, list[int]] = {}
    if func is None:
        return definitions
    for node in ast.walk(func):
        if getattr(node, "lineno", 10**9) >= line:
            continue
        targets = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.For):
            targets = [node.target]
        for target in targets:
            for name in ast.walk(target):
                if isinstance(name, ast.Name) and isinstance(name.ctx, ast.Store):
                    definitions.setdefault(name.id, []).append(node.lineno)
    return definitions


def _extract_localized_statement(localized_code: str, filename: str, line: int) -> str:
    active = False
    for raw_line in localized_code.splitlines():
        header = re.match(r"###\s+(.+)", raw_line.strip())
        if header:
            active = header.group(1).strip() == filename
            continue
        if not active:
            continue
        match = re.match(r"\s*(\d+)\|\s?(.*)", raw_line)
        if match and int(match.group(1)) == line:
            return match.group(2).rstrip()
    return ""


def build_target_context(
    *,
    dataset: dict[str, Any],
    repo_root: Path,
    source_dir: Path,
) -> dict[str, Any]:
    target = choose_target_location(dataset)
    filename = target.get("file", "")
    line = int(target.get("line") or 0)
    localized_code = dataset.get("localized_code") or ""
    path = resolve_repo_file(repo_root, source_dir, filename) if filename else None

    if not path or not line:
        statement = _extract_localized_statement(localized_code, filename, line)
        return {
            "target_location": {"file": filename, "function": "", "line": line, "statement": statement},
            "selection_reason": target.get("selection_reason", "missing file or line"),
            "function_source": "",
            "guard_conditions": [],
            "variables": [],
            "variable_definitions": {},
            "parameters": [],
            "source_available": False,
        }

    source = path.read_text(errors="ignore")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        statement = source.splitlines()[line - 1].strip() if 0 < line <= len(source.splitlines()) else ""
        return {
            "target_location": {"file": filename, "function": "", "line": line, "statement": statement},
            "selection_reason": target.get("selection_reason", "syntax error fallback"),
            "function_source": "",
            "guard_conditions": [],
            "variables": [],
            "variable_definitions": {},
            "parameters": [],
            "source_available": True,
        }

    _ParentAnnotator().visit(tree)
    func = _enclosing_function(tree, line)
    stmt = _nearest_statement(tree, line)
    statement = ast.get_source_segment(source, stmt) if stmt else ""
    if not statement:
        lines = source.splitlines()
        statement = lines[line - 1].strip() if 0 < line <= len(lines) else ""

    function_source = ast.get_source_segment(source, func) if func else ""
    params = []
    if func:
        args = list(func.args.posonlyargs) + list(func.args.args) + list(func.args.kwonlyargs)
        params = [arg.arg for arg in args]
        if func.args.vararg:
            params.append(func.args.vararg.arg)
        if func.args.kwarg:
            params.append(func.args.kwarg.arg)

    definitions = _defined_names_before(func, line)
    variables = _loaded_names(stmt)
    return {
        "target_location": {
            "file": filename,
            "function": getattr(func, "name", ""),
            "line": line,
            "statement": statement.strip(),
        },
        "selection_reason": target.get("selection_reason", "top suspicious line"),
        "function_source": function_source,
        "guard_conditions": _guard_conditions(source, stmt),
        "variables": variables,
        "variable_definitions": {name: definitions.get(name, []) for name in variables},
        "parameters": [name for name in variables if name in params],
        "source_available": True,
        "source_match_hint": difflib.get_close_matches(statement.strip(), localized_code.splitlines(), n=1),
    }
