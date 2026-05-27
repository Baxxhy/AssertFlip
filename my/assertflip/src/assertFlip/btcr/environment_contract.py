import ast
from collections import Counter
from pathlib import Path
from typing import Any

from .io import resolve_repo_file


def _decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _decorator_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ""


def _parse_source(source: str) -> ast.Module | None:
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def _read_test_file_context(repo_root: Path, source_dir: Path, related_tests: list[dict[str, Any]]) -> dict[str, str]:
    files = {}
    for test in related_tests:
        filename = test.get("file") or test.get("path")
        if not filename or filename in files:
            continue
        path = resolve_repo_file(repo_root, source_dir, filename)
        if path:
            try:
                files[filename] = path.read_text(errors="ignore")
            except Exception:
                pass
    return files


def build_environment_contract(
    *,
    instance_id: str,
    related_tests: list[dict[str, Any]],
    repo_root: Path,
    source_dir: Path,
) -> dict[str, Any]:
    file_counts = Counter(
        test.get("file") or test.get("path")
        for test in related_tests
        if test.get("file") or test.get("path")
    )
    insert_file = file_counts.most_common(1)[0][0] if file_counts else ""
    test_file_context = _read_test_file_context(repo_root, source_dir, related_tests)
    snippets = [test.get("code_content") or test.get("source") or test.get("code") or "" for test in related_tests]
    sources = list(test_file_context.values()) + snippets

    imports: list[str] = []
    fixtures: list[str] = []
    helpers: list[str] = []
    globals_: list[str] = []
    uses_pytest = False
    uses_unittest = False
    uses_bare_assert = False
    uses_self_assert = False
    uses_pytest_raises = False

    for source in sources:
        tree = _parse_source(source)
        if tree is None:
            if "pytest" in source:
                uses_pytest = True
            if "self.assert" in source:
                uses_unittest = True
            continue
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                line = ast.get_source_segment(source, node)
                if line and line not in imports:
                    imports.append(line)
                    if "pytest" in line:
                        uses_pytest = True
                    if "unittest" in line:
                        uses_unittest = True
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = [_decorator_name(d) for d in node.decorator_list]
                if any(d.endswith("pytest.fixture") or d == "fixture" for d in decorators):
                    fixtures.append(node.name)
                    uses_pytest = True
                elif not node.name.startswith("test_"):
                    helpers.append(node.name)
                for child in ast.walk(node):
                    if isinstance(child, ast.Assert):
                        uses_bare_assert = True
                    elif isinstance(child, ast.Call):
                        call_name = _decorator_name(child.func)
                        if call_name.startswith("self.assert"):
                            uses_self_assert = True
                        if call_name == "pytest.raises":
                            uses_pytest = True
                            uses_pytest_raises = True
            elif isinstance(node, ast.ClassDef):
                if any(base_name.endswith("TestCase") for base_name in [_decorator_name(b) for b in node.bases]):
                    uses_unittest = True
                for child in ast.walk(node):
                    if isinstance(child, ast.Call) and _decorator_name(child.func).startswith("self.assert"):
                        uses_self_assert = True
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                line = ast.get_source_segment(source, node)
                if line and len(line) < 300:
                    globals_.append(line)

    if uses_unittest and not uses_pytest:
        framework = "unittest"
    else:
        framework = "pytest"

    if uses_self_assert:
        assertion_style = "unittest self.assert* methods"
    elif uses_pytest_raises:
        assertion_style = "pytest assert statements and pytest.raises"
    elif uses_bare_assert:
        assertion_style = "plain assert statements"
    else:
        assertion_style = "project-local style inferred from related tests"

    return {
        "instance_id": instance_id,
        "insert_file": insert_file,
        "imports": imports[:40],
        "fixtures": sorted(set(fixtures))[:30],
        "helpers": sorted(set(helpers))[:30],
        "global_objects": globals_[:40],
        "assertion_style": assertion_style,
        "test_framework": framework,
        "unstable_patterns_to_avoid": [
            "Do not invent imports that are absent from related tests unless required by the issue.",
            "Do not call pytest.main or execute tests at module import time.",
            "Avoid network, wall-clock sleeps, randomness without a fixed seed, and broad filesystem writes.",
            "Prefer existing fixtures/helpers/global objects from the insert file when they fit the issue.",
        ],
        "related_test_files": list(file_counts.keys()),
    }
