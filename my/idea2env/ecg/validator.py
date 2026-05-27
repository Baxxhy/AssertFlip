from __future__ import annotations

import ast
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

from .contracts import ContractValidationReport, EnvironmentContractGraph
from .scaffold import (
    LOCKED_HASH_PREFIX,
    SLOT_ACT_BEGIN,
    SLOT_ACT_END,
    SLOT_ARRANGE_BEGIN,
    SLOT_ARRANGE_END,
    SLOT_ORACLE_BEGIN,
    SLOT_ORACLE_END,
    locked_region_hash,
)


def _hash_from_code(code: str) -> str | None:
    for line in code.splitlines():
        if line.startswith(LOCKED_HASH_PREFIX):
            return line.split(":", 1)[1].strip()
    return None


def _without_hash(code: str) -> str:
    return "\n".join(line for line in code.splitlines() if not line.startswith(LOCKED_HASH_PREFIX))


def _test_python() -> str:
    preferred = Path("/opt/miniconda3/envs/testbed/bin/python")
    if preferred.exists():
        return str(preferred)
    return sys.executable


def _pytest_collect_command(test_command: str, test_path: Path) -> list[str]:
    parts = shlex.split(test_command)
    pytest_args = parts[1:] if parts and Path(parts[0]).name == "pytest" else []
    return [_test_python(), "-m", "pytest", "--collect-only", "-q", *pytest_args, str(test_path)]


def validate_contract(
    test_path: Path,
    repo_root: Path,
    graph: EnvironmentContractGraph,
    scaffold: str | None = None,
    *,
    test_command: str = "pytest",
) -> ContractValidationReport:
    violations: list[str] = []
    warnings: list[str] = []
    details: dict[str, object] = {"test_path": str(test_path), "repo_root": str(repo_root)}
    code = test_path.read_text(errors="ignore")

    try:
        ast.parse(code)
    except SyntaxError as exc:
        violations.append(f"syntax error: {exc}")

    has_contract_markers = LOCKED_HASH_PREFIX in code or any(
        marker in code
        for marker in (
            SLOT_ARRANGE_BEGIN,
            SLOT_ARRANGE_END,
            SLOT_ACT_BEGIN,
            SLOT_ACT_END,
            SLOT_ORACLE_BEGIN,
            SLOT_ORACLE_END,
        )
    )
    details["contract_marked"] = has_contract_markers
    if has_contract_markers:
        expected_hash = _hash_from_code(scaffold or code)
        actual_hash = locked_region_hash(_without_hash(code))
        details["locked_hash_expected"] = expected_hash
        details["locked_hash_actual"] = actual_hash
        if expected_hash and actual_hash != expected_hash:
            violations.append("locked region hash mismatch")

        for marker in (
            SLOT_ARRANGE_BEGIN,
            SLOT_ARRANGE_END,
            SLOT_ACT_BEGIN,
            SLOT_ACT_END,
            SLOT_ORACLE_BEGIN,
            SLOT_ORACLE_END,
        ):
            if marker not in code:
                violations.append(f"missing slot boundary: {marker}")

    if "pytest.main(" in code:
        violations.append("test must not call pytest.main")
    if "pip install" in code or "subprocess" in code and "pip" in code:
        warnings.append("test appears to invoke package installation or subprocess")

    if not str(test_path).startswith(str(repo_root)) and str(repo_root) != ".":
        warnings.append("test path is outside repo root")

    preflight_mode = os.getenv("CONTRACT_BRT_PREFLIGHT_MODE", "syntax").strip().lower()
    details["preflight_mode"] = preflight_mode
    run_import_dry_run = preflight_mode in {"import", "collect", "full"}
    run_pytest_collect = preflight_mode in {"collect", "full"}

    if not violations and run_import_dry_run:
        import_cmd = [
            _test_python(),
            "-c",
            (
                "import importlib.util, sys; "
                f"p={str(test_path)!r}; "
                "spec=importlib.util.spec_from_file_location('contract_brt_preflight', p); "
                "m=importlib.util.module_from_spec(spec); "
                "spec.loader.exec_module(m)"
            ),
        ]
        proc = subprocess.run(import_cmd, cwd=repo_root, capture_output=True, text=True, timeout=30, check=False)
        details["import_dry_run_rc"] = proc.returncode
        if proc.returncode:
            warnings.append("import dry-run failed: " + (proc.stderr or proc.stdout or "no output")[:1000])

    if run_pytest_collect and "pytest" in test_command:
        collect_cmd = _pytest_collect_command(test_command, test_path)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo_root) + (f":{env['PYTHONPATH']}" if env.get("PYTHONPATH") else "")
        proc = subprocess.run(collect_cmd, cwd=repo_root, env=env, capture_output=True, text=True, timeout=60, check=False)
        details["pytest_collect_rc"] = proc.returncode
        if proc.returncode:
            warnings.append("pytest collect failed: " + (proc.stderr or proc.stdout or "no output")[:1000])

    return ContractValidationReport(passed=not violations, violations=violations, warnings=warnings, details=details)


def validate_code_in_temp(
    code: str,
    repo_root: Path,
    graph: EnvironmentContractGraph,
    scaffold: str,
    *,
    test_command: str = "pytest",
    suffix: str = ".py",
) -> ContractValidationReport:
    with tempfile.NamedTemporaryFile("w", suffix=suffix, prefix="contract_brt_", dir=repo_root, delete=False) as handle:
        handle.write(code)
        temp_path = Path(handle.name)
    try:
        return validate_contract(temp_path, repo_root, graph, scaffold, test_command=test_command)
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass
