from pathlib import Path
from typing import Any

from .environment_contract import build_environment_contract
from .io import dump_json, load_related_tests
from .probe_validation import save_probe_validation, write_probe_placeholder
from .target_context import build_target_context
from .trigger_contract import build_probe_test_plan, build_trigger_contract


def _result_dir(base_dir: Path, instance_id: str) -> Path:
    return base_dir / instance_id


def build_btcr_context(
    *,
    dataset: dict[str, Any],
    repo_root: Path,
    source_dir: Path,
    related_tests_path: Path | None,
    output_dir: Path,
    enabled: bool = True,
) -> dict[str, Any]:
    instance_id = dataset.get("instance_id", "unknown_instance")
    instance_dir = _result_dir(output_dir, instance_id)
    if not enabled:
        context = {
            "enabled": False,
            "environment_contract": {},
            "target_context": {},
            "trigger_contract": {},
            "probe_test_plan": {},
            "related_tests": [],
            "artifact_dir": str(instance_dir),
        }
        dump_json(instance_dir / "btcr_context.json", context)
        return context

    related_tests = load_related_tests(related_tests_path, instance_id)
    environment_contract = build_environment_contract(
        instance_id=instance_id,
        related_tests=related_tests,
        repo_root=repo_root,
        source_dir=source_dir,
    )
    target_context = build_target_context(
        dataset=dataset,
        repo_root=repo_root,
        source_dir=source_dir,
    )
    trigger_contract = build_trigger_contract(
        problem_statement=dataset.get("problem_statement", ""),
        patch=dataset.get("patch", ""),
        target_context=target_context,
        related_tests=related_tests,
        repo_root=repo_root,
    )
    probe_test_plan = build_probe_test_plan(environment_contract, trigger_contract)

    context = {
        "enabled": True,
        "environment_contract": environment_contract,
        "target_context": target_context,
        "trigger_contract": trigger_contract,
        "probe_test_plan": probe_test_plan,
        "related_tests": related_tests[:10],
        "artifact_dir": str(instance_dir),
    }

    dump_json(instance_dir / "environment_contract.json", environment_contract)
    dump_json(instance_dir / "target_context.json", target_context)
    dump_json(instance_dir / "trigger_contract.json", trigger_contract)
    dump_json(instance_dir / "probe_test_plan.json", probe_test_plan)
    dump_json(instance_dir / "related_tests_used.json", related_tests)
    dump_json(instance_dir / "btcr_context.json", context)
    write_probe_placeholder(instance_dir / "probe_test.py", probe_test_plan)
    save_probe_validation(
        instance_dir / "probe_validation_result.json",
        {
            "status": "skipped",
            "failure_type": None,
            "reason": "Minimal BTCR integration writes a probe plan and lets the original AssertFlip validation run the generated test.",
        },
    )
    return context
