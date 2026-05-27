from __future__ import annotations

import ast
import configparser
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .contracts import EnvironmentContractGraph


CONFIG_FILES = ("pytest.ini", "tox.ini", "pyproject.toml", "setup.cfg")
LIFECYCLE_NAMES = {"setUp", "tearDown", "setUpTestData", "setup_method", "teardown_method"}


def _decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _decorator_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ""


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return _decorator_name(node)


def _parse(source: str) -> ast.Module | None:
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def _import_aliases(node: ast.Import | ast.ImportFrom) -> list[tuple[str, str]]:
    if isinstance(node, ast.Import):
        return [(alias.name, alias.asname or alias.name.split(".")[0]) for alias in node.names]
    module = node.module or ""
    level = "." * node.level
    return [
        (f"{level}{module}.{alias.name}" if module else f"{level}{alias.name}", alias.asname or alias.name)
        for alias in node.names
    ]


def _resolve_related_tests(path: Path | None, instance_id: str) -> list[dict[str, Any]]:
    if not path or not path.exists():
        return []
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        value = data.get(instance_id, [])
        return value if isinstance(value, list) else []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("instance_id") == instance_id:
                tests = item.get("related_tests", item.get("tests", []))
                return tests if isinstance(tests, list) else []
    return []


def _candidate_path(repo_root: Path, test_dir: str, filename: str) -> Path | None:
    candidates = [
        repo_root / filename,
        repo_root / test_dir / filename,
        repo_root / filename.lstrip("/"),
    ]
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None


def _read_sources(repo_root: Path, test_dir: str, related_tests: list[dict[str, Any]]) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    seen_files: set[str] = set()
    for test in related_tests:
        filename = str(test.get("file") or test.get("path") or "")
        snippet = test.get("code_content") or test.get("source") or test.get("code") or ""
        if snippet:
            sources.append((filename or "<related-snippet>", str(snippet)))
        if filename and filename not in seen_files:
            seen_files.add(filename)
            path = _candidate_path(repo_root, test_dir, filename)
            if path:
                sources.append((str(path.relative_to(repo_root)), path.read_text(errors="ignore")))

    for conftest in sorted(repo_root.glob("**/conftest.py"))[:20]:
        if any(part in {".git", ".tox", ".venv", "venv", "__pycache__"} for part in conftest.parts):
            continue
        try:
            sources.append((str(conftest.relative_to(repo_root)), conftest.read_text(errors="ignore")))
        except OSError:
            pass
    return sources


def _scan_configs(repo_root: Path, graph: EnvironmentContractGraph) -> None:
    for name in CONFIG_FILES:
        path = repo_root / name
        if not path.exists():
            continue
        graph.add_node(f"config:{name}", "RunnerContract", name, path=name)
        graph.add_edge("test_runner", "configured_by", f"config:{name}")
        if name.endswith(".ini") or name == "setup.cfg" or name == "tox.ini":
            parser = configparser.ConfigParser()
            try:
                parser.read(path)
            except configparser.Error:
                continue
            for section in parser.sections():
                if "pytest" in section or section == "tool:pytest":
                    graph.add_node(f"pytest-config:{section}", "RunnerContract", section)
                    graph.add_edge(f"config:{name}", "declares", f"pytest-config:{section}")
        elif name == "pyproject.toml":
            text = path.read_text(errors="ignore")
            if "[tool.pytest" in text:
                graph.add_node("pytest-config:pyproject", "RunnerContract", "pyproject pytest")
                graph.add_edge(f"config:{name}", "declares", "pytest-config:pyproject")


def _extract_from_source(graph: EnvironmentContractGraph, filename: str, source: str) -> None:
    tree = _parse(source)
    if tree is None:
        return
    graph.add_node(f"file:{filename}", "RunnerContract", filename, file=filename)
    graph.add_edge("test_file", "located_in", f"file:{filename}")

    import_alias: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for full, alias in _import_aliases(node):
                node_id = f"import:{full}"
                graph.add_node(node_id, "ImportContract", full, alias=alias, file=filename)
                graph.add_edge(f"file:{filename}", "requires_import", node_id)
                import_alias[alias] = full

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "pytestmark":
                    mark_id = f"mark:{ast.get_source_segment(source, node.value) or 'pytestmark'}"
                    graph.add_node(mark_id, "RunnerContract", "pytestmark", file=filename)
                    graph.add_edge(f"file:{filename}", "uses_marker", mark_id)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _extract_function(graph, filename, node)
        if isinstance(node, ast.ClassDef):
            class_id = f"class:{node.name}"
            graph.add_node(class_id, "ClassContract", node.name, file=filename)
            graph.add_edge(f"file:{filename}", "declares", class_id)
            for base in node.bases:
                base_name = _decorator_name(base)
                if base_name:
                    base_id = f"class:{base_name}"
                    graph.add_node(base_id, "ClassContract", base_name, file=filename)
                    graph.add_edge(class_id, "inherits", base_id)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    _extract_function(graph, filename, item, owner=class_id)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            call = _call_name(node)
            if call in {"settings.configure", "django.setup", "override_settings"} or call.endswith(".override_settings"):
                contract_id = f"config-call:{call}"
                graph.add_node(contract_id, "ConfigContract", call, file=filename)
                graph.add_edge(f"file:{filename}", "requires_config", contract_id)
            if call in {"mock.patch", "patch", "unittest.mock.patch"} or call.endswith(".patch"):
                mock_id = f"mock:{call}"
                graph.add_node(mock_id, "MockContract", call, file=filename)
                graph.add_edge(f"file:{filename}", "uses_mock", mock_id)
            if call.startswith("monkeypatch."):
                mock_id = f"mock:{call}"
                graph.add_node(mock_id, "MockContract", call, file=filename)
                graph.add_edge(f"file:{filename}", "uses_mock", mock_id)
            if "." in call and not call.startswith("self.assert"):
                api_id = f"api:{call}"
                graph.add_node(api_id, "APIUsageContract", call, file=filename)
                graph.add_edge(f"file:{filename}", "uses", api_id)


def _extract_function(
    graph: EnvironmentContractGraph,
    filename: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    owner: str | None = None,
) -> None:
    decorators = [_decorator_name(dec) for dec in node.decorator_list]
    fn_id = f"function:{node.name}"
    if node.name in LIFECYCLE_NAMES:
        graph.add_node(fn_id, "LifecycleContract", node.name, file=filename)
        graph.add_edge(owner or f"file:{filename}", "has_lifecycle", fn_id)
    elif any(dec.endswith("pytest.fixture") or dec == "fixture" for dec in decorators):
        graph.add_node(
            fn_id,
            "FixtureContract",
            node.name,
            file=filename,
            decorators=decorators,
            declared=True,
            global_fixture=filename.endswith("conftest.py"),
        )
        graph.add_edge(f"file:{filename}", "declares_fixture", fn_id)
    elif node.name.startswith("test_"):
        graph.add_node(fn_id, "RunnerContract", node.name, file=filename)
        graph.add_edge(owner or f"file:{filename}", "declares_test", fn_id)

    for dec in decorators:
        if dec.startswith("pytest.mark") or dec.startswith("mark."):
            mark_id = f"mark:{dec}"
            graph.add_node(mark_id, "RunnerContract", dec, file=filename)
            graph.add_edge(fn_id, "uses_marker", mark_id)
        if "patch" in dec:
            mock_id = f"mock:{dec}"
            graph.add_node(mock_id, "MockContract", dec, file=filename)
            graph.add_edge(fn_id, "uses_mock", mock_id)

    parametrized_args: set[str] = set()
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call) and _decorator_name(dec.func).endswith("parametrize") and dec.args:
            first_arg = dec.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                raw = first_arg.value.replace(" ", "")
                parametrized_args.update(part for part in raw.replace("(", "").replace(")", "").split(",") if part)

    for arg in node.args.args:
        if arg.arg not in {"self", "cls"} and node.name.startswith("test_"):
            if arg.arg in parametrized_args:
                continue
            fixture_id = f"fixture:{arg.arg}"
            graph.add_node(fixture_id, "FixtureContract", arg.arg, file=filename, declared=False)
            graph.add_edge(fn_id, "requires", fixture_id)


def build_environment_contract_graph(
    *,
    instance_id: str,
    repo_root: Path,
    test_dir: str,
    related_tests_path: Path | None = None,
    related_tests: list[dict[str, Any]] | None = None,
    issue_text: str = "",
    localized_files: list[str] | None = None,
    runner: str = "pytest",
) -> EnvironmentContractGraph:
    repo_root = Path(repo_root)
    related_tests = related_tests if related_tests is not None else _resolve_related_tests(related_tests_path, instance_id)
    file_counts = Counter(str(test.get("file") or test.get("path") or "") for test in related_tests)

    graph = EnvironmentContractGraph(
        instance_id=instance_id,
        repo_root=str(repo_root),
        test_dir=test_dir,
        runner=runner,
        metadata={
            "issue_excerpt": issue_text[:500],
            "localized_files": localized_files or [],
            "related_test_files": [item for item, _ in file_counts.most_common(20) if item],
        },
    )
    graph.add_node("test_runner", "RunnerContract", runner, command=runner)
    if test_dir:
        graph.add_node(f"test_dir:{test_dir}", "RunnerContract", test_dir, path=test_dir)
        graph.add_edge("test_file", "located_in", f"test_dir:{test_dir}")

    for filename, source in _read_sources(repo_root, test_dir, related_tests):
        _extract_from_source(graph, filename, source)
    _scan_configs(repo_root, graph)
    return graph
