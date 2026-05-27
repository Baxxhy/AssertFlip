from __future__ import annotations

import ast
import hashlib
import re
from textwrap import indent

from .contracts import ContractNode, EnvironmentContractGraph


LOCKED_IMPORTS_BEGIN = "# ===== CONTRACT-BRT LOCKED IMPORTS BEGIN ====="
LOCKED_IMPORTS_END = "# ===== CONTRACT-BRT LOCKED IMPORTS END ====="
LOCKED_CLASS_BEGIN = "# ===== CONTRACT-BRT LOCKED CLASS BEGIN ====="
LOCKED_CLASS_END = "# ===== CONTRACT-BRT LOCKED CLASS END ====="
LOCKED_HASH_PREFIX = "# CONTRACT-BRT LOCKED HASH:"
SLOT_ARRANGE_BEGIN = "# ===== CONTRACT-BRT SLOT ARRANGE BEGIN ====="
SLOT_ARRANGE_END = "# ===== CONTRACT-BRT SLOT ARRANGE END ====="
SLOT_ACT_BEGIN = "# ===== CONTRACT-BRT SLOT ACT BEGIN ====="
SLOT_ACT_END = "# ===== CONTRACT-BRT SLOT ACT END ====="
SLOT_ORACLE_BEGIN = "# ===== CONTRACT-BRT SLOT ORACLE BEGIN ====="
SLOT_ORACLE_END = "# ===== CONTRACT-BRT SLOT ORACLE END ====="


def _safe_name(instance_id: str) -> str:
    return re.sub(r"[^0-9A-Za-z_]", "_", instance_id)


def _node_labels(graph: EnvironmentContractGraph, node_type: str) -> list[str]:
    labels = []
    for node in graph.nodes_by_type(node_type):
        value = node.label or node.id.split(":", 1)[-1]
        if value and value not in labels:
            labels.append(value)
    return labels


def _import_line(node: ContractNode) -> str | None:
    value = node.label or node.id.removeprefix("import:")
    if value.startswith("."):
        return None
    parts = value.split(".")
    if len(parts) >= 2 and parts[-1][:1].isupper():
        return f"from {'.'.join(parts[:-1])} import {parts[-1]}"
    if len(parts) >= 2 and parts[-1] in {"raises", "mark", "fixture"}:
        return f"import {parts[0]}"
    return f"import {value.split('.')[0]}"


def _is_django_graph(graph: EnvironmentContractGraph) -> bool:
    project = graph.metadata.get("project_name", "")
    labels = " ".join(_node_labels(graph, "ImportContract") + _node_labels(graph, "ClassContract"))
    return project == "django" or "django.test" in labels


def _select_imports(graph: EnvironmentContractGraph) -> list[str]:
    imports: list[str] = []

    def add_front(line: str) -> None:
        if line in imports:
            imports.remove(line)
        imports.insert(0, line)

    def matches_symbol(label: str, symbol: str) -> bool:
        return label == symbol or label.endswith(f".{symbol}")

    import_labels = _node_labels(graph, "ImportContract")
    api_labels = _node_labels(graph, "APIUsageContract")
    class_labels = _node_labels(graph, "ClassContract")
    labels = " ".join(import_labels + api_labels + class_labels)

    if _is_django_graph(graph):
        base_class = _select_base_class(graph) or "SimpleTestCase"
        add_front(f"from django.test import {base_class}")
        if "HttpResponse" in labels:
            add_front("from django.http import HttpResponse")

    uses_pytest = any(
        node.type == "FixtureContract" or node.id.startswith("mark:") or (node.label or "").startswith("pytest")
        for node in graph.nodes
    )
    if uses_pytest and not _is_django_graph(graph):
        add_front("import pytest")
    return imports[:12] or ["import pytest"]


def _select_base_class(graph: EnvironmentContractGraph) -> str | None:
    if not _is_django_graph(graph):
        return None
    class_labels = _node_labels(graph, "ClassContract")
    for preferred in ("SimpleTestCase", "TestCase", "TransactionTestCase"):
        if any(label == preferred or label.endswith(f".{preferred}") for label in class_labels):
            return preferred
    labels = " ".join(class_labels + _node_labels(graph, "ImportContract"))
    if "django." in labels:
        return "SimpleTestCase"
    return None


def _select_fixtures(graph: EnvironmentContractGraph) -> list[str]:
    # Keep fixture knowledge in the ECG/prompt, but do not force fixture
    # parameters into the locked wrapper. Project-wide conftest fixtures are
    # often optional helpers, and locking them here turns examples into hard
    # environment requirements for unrelated generated tests.
    return []


def locked_region_hash(scaffold_without_hash: str) -> str:
    locked_parts = []
    capture = False
    for line in scaffold_without_hash.splitlines():
        stripped = line.strip()
        if stripped in {LOCKED_IMPORTS_BEGIN, LOCKED_CLASS_BEGIN}:
            capture = True
        if capture:
            locked_parts.append(line)
        if stripped in {LOCKED_IMPORTS_END, LOCKED_CLASS_END}:
            capture = False
    data = "\n".join(locked_parts).encode()
    return hashlib.sha256(data).hexdigest()[:16]


def build_locked_scaffold(graph: EnvironmentContractGraph, instance_id: str) -> str:
    test_name = f"test_contract_brt_{_safe_name(instance_id)}"
    base_class = _select_base_class(graph)
    fixtures = _select_fixtures(graph)
    imports = "\n".join(_select_imports(graph))

    if base_class:
        class_name = "ContractBRTEnvironmentTests"
        body = f"""{LOCKED_CLASS_BEGIN}
class {class_name}({base_class}):
{LOCKED_CLASS_END}

    def {test_name}(self):
        {SLOT_ARRANGE_BEGIN}
        pass
        {SLOT_ARRANGE_END}

        {SLOT_ACT_BEGIN}
        pass
        {SLOT_ACT_END}

        {SLOT_ORACLE_BEGIN}
        pass
        {SLOT_ORACLE_END}
"""
    else:
        fixture_args = ", ".join(fixtures)
        body = f"""{LOCKED_CLASS_BEGIN}
def {test_name}({fixture_args}):
{LOCKED_CLASS_END}
    {SLOT_ARRANGE_BEGIN}
    pass
    {SLOT_ARRANGE_END}

    {SLOT_ACT_BEGIN}
    pass
    {SLOT_ACT_END}

    {SLOT_ORACLE_BEGIN}
    pass
    {SLOT_ORACLE_END}
"""

    scaffold = f"""{LOCKED_IMPORTS_BEGIN}
{imports}
{LOCKED_IMPORTS_END}

{body}
"""
    return f"{LOCKED_HASH_PREFIX} {locked_region_hash(scaffold)}\n{scaffold}"


def build_prompt_prefix(graph: EnvironmentContractGraph) -> str:
    has_fixtures = bool(_node_labels(graph, "FixtureContract"))
    has_django = _is_django_graph(graph)
    has_pytest = has_fixtures or graph.runner.startswith("pytest")

    hints = [
        "Primary objective: write the AssertFlip pass-first test. It should pass on the buggy version while expressing the current buggy behavior.",
        "Use the recovered Environment Contract Graph only as lightweight setup guidance, not as a template to copy.",
        f"Project runner/location hint: runner={graph.runner}, test_dir={graph.test_dir}.",
        "Prefer nearby project-native test style only when it prevents mechanical import/setup/runner errors.",
        "Do not copy optional imports or dependencies from related tests unless the bug-triggering logic truly needs them.",
        "Do not call pytest.main(), install packages, use network access, or execute tests at import time.",
    ]
    if has_django:
        hints.append(
            "For Django cases, prefer Django's own test style such as django.test SimpleTestCase/TestCase and project runner conventions when a wrapper is needed."
        )
    if has_pytest:
        hints.append("For pytest cases, use fixtures only when they are directly required by the generated test.")

    return f"""
<CONTRACT_BRT_ENV_HINT>
This is a lightweight project-environment hint. It is secondary to the bug-reproduction objective.
{chr(10).join(f"- {hint}" for hint in hints)}
</CONTRACT_BRT_ENV_HINT>
"""


def _strip_body_indent(stmt_lines: list[str]) -> list[str]:
    indents = [len(line) - len(line.lstrip(" ")) for line in stmt_lines if line.strip()]
    base = min(indents) if indents else 0
    if base <= 0:
        return stmt_lines
    return [line[base:] if line.startswith(" " * base) else line for line in stmt_lines]


def _first_test_statements(code: str) -> list[list[str]]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return [[line] for line in code.splitlines() if line.strip()]
    lines = code.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            statements: list[list[str]] = []
            for stmt in node.body:
                start = getattr(stmt, "lineno", None)
                end = getattr(stmt, "end_lineno", None)
                if start and end:
                    statements.append(_strip_body_indent(lines[start - 1 : end]))
            return statements
    return [[line] for line in code.splitlines() if line.strip() and not line.strip().startswith(("import ", "from "))]


def _module_import_statements(code: str) -> list[list[str]]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    lines = code.splitlines()
    imports: list[list[str]] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None)
            if start and end:
                imports.append(lines[start - 1 : end])
    return imports


def _replace_slot(scaffold: str, begin: str, end: str, body: list[str], spaces: int) -> str:
    block = indent("\n".join(body) if body else "pass", " " * spaces)
    pattern = re.compile(re.escape(begin) + r"\n.*?\n\s*" + re.escape(end), re.DOTALL)
    replacement = f"{begin}\n{block}\n{' ' * spaces}{end}"
    return pattern.sub(replacement, scaffold, count=1)


def merge_slots(scaffold: str, llm_code: str) -> str:
    statements = _module_import_statements(llm_code) + _first_test_statements(llm_code)
    if not statements:
        return scaffold
    oracle_stmts: list[list[str]] = []
    prefix_stmts: list[list[str]] = []
    for stmt in statements:
        joined = "\n".join(stmt).lstrip()
        if joined.startswith("assert ") or ".assert" in joined or "pytest.raises" in joined:
            oracle_stmts.append(stmt)
        else:
            prefix_stmts.append(stmt)
    if not oracle_stmts and prefix_stmts:
        oracle_stmts = [prefix_stmts.pop()]
    arrange = [line for stmt in prefix_stmts for line in stmt] or ["pass"]
    act = ["pass"]
    oracle = [line for stmt in oracle_stmts for line in stmt] or ["pass"]
    spaces = 8 if "\n    def " in scaffold else 4
    merged = _replace_slot(scaffold, SLOT_ARRANGE_BEGIN, SLOT_ARRANGE_END, arrange, spaces)
    merged = _replace_slot(merged, SLOT_ACT_BEGIN, SLOT_ACT_END, act, spaces)
    merged = _replace_slot(merged, SLOT_ORACLE_BEGIN, SLOT_ORACLE_END, oracle, spaces)
    return merged
