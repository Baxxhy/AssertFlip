from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .contracts import ContractValidationReport
from .pipeline import ContractBRT, ContractContext, classify_execution_failure, make_environment_feedback


def is_enabled(args_or_env: Any = None) -> bool:
    if args_or_env is not None and hasattr(args_or_env, "contract_brt"):
        return bool(getattr(args_or_env, "contract_brt"))
    return os.getenv("CONTRACT_BRT_ENABLE", "1") not in {"0", "false", "False", "no"}


def prepare_instance_context(
    *,
    args: Any,
    dataset: dict[str, Any],
    repo_root: Path,
    test_dir: str,
    runner: str,
) -> ContractContext | None:
    if not is_enabled(args):
        return None
    contract = ContractBRT(
        root=Path(getattr(args, "contract_root", None) or os.getenv("CONTRACT_BRT_ROOT", ".")),
        contract_dir=Path(getattr(args, "contract_dir", None) or os.getenv("CONTRACT_BRT_CONTRACT_DIR", "contracts")),
        generated_test_dir=Path(
            getattr(args, "generated_test_dir", None) or os.getenv("CONTRACT_BRT_GENERATED_TEST_DIR", "generated_tests")
        ),
        strictness=getattr(args, "contract_strictness", "repair"),
        scaffold_mode=getattr(args, "contract_scaffold_mode", None),
    )
    localized_files = [item.get("filename", "") for item in dataset.get("line_level_localization", []) if isinstance(item, dict)]
    return contract.build_contract(
        instance_id=dataset.get("instance_id", "unknown_instance"),
        repo_root=repo_root,
        test_dir=test_dir,
        related_tests_path=Path(getattr(args, "related_tests", "")) if getattr(args, "related_tests", None) else None,
        issue_text=dataset.get("problem_statement", ""),
        localized_files=localized_files,
        runner=runner,
    )


def augment_messages(messages: list[dict[str, Any]], context: ContractContext | None) -> list[dict[str, Any]]:
    if context is None:
        return messages
    contract = ContractBRT(
        root=Path(os.getenv("CONTRACT_BRT_ROOT", ".")),
        contract_dir=context.artifact_dir.parent,
        generated_test_dir=context.generated_dir.parent,
        scaffold_mode=os.getenv("CONTRACT_BRT_SCAFFOLD_MODE", "off"),
    )
    return contract.augment_generation_prompt(messages, context)


def postprocess_test_code(test_code: str, context: ContractContext | None, *, label: str = "candidate") -> str:
    if context is None:
        return test_code
    contract = ContractBRT(
        root=Path(os.getenv("CONTRACT_BRT_ROOT", ".")),
        contract_dir=context.artifact_dir.parent,
        generated_test_dir=context.generated_dir.parent,
        scaffold_mode=os.getenv("CONTRACT_BRT_SCAFFOLD_MODE", "off"),
    )
    return contract.postprocess_generated_test(test_code, context, label=label)


def classify_failure(error_text: str | None) -> str | None:
    return classify_execution_failure(error_text)


def make_execution_environment_feedback(
    error_text: str | None,
    context: ContractContext | None,
    test_code: str | None = None,
) -> str:
    if context is None or not error_text:
        return ""
    if not classify_execution_failure(error_text):
        return ""
    return make_environment_feedback(error_text, context.graph, test_code)


def preflight_test_code(
    test_code: str,
    *,
    args: Any,
    context: ContractContext | None,
    label: str,
) -> ContractValidationReport | None:
    if context is None:
        return None
    contract = ContractBRT(
        root=Path(os.getenv("CONTRACT_BRT_ROOT", ".")),
        contract_dir=context.artifact_dir.parent,
        generated_test_dir=context.generated_dir.parent,
        strictness=getattr(args, "contract_strictness", "repair"),
    )
    return contract.preflight_code(
        test_code,
        repo_root=Path.cwd(),
        context=context,
        test_command=getattr(args, "test_cmd", "pytest"),
        label=label,
    )


def make_refinement_feedback(report: ContractValidationReport) -> str:
    problems = "\n".join(f"- {item}" for item in report.violations) or "- no hard violations"
    warnings = "\n".join(f"- {item}" for item in report.warnings[:5]) or "- no warnings"
    return f"""CONTRACT_BRT_PREFLIGHT_FAILED
The generated test violates the recovered Environment Contract Graph before the real test run.
Make the smallest possible environment/setup repair and preserve the bug-triggering logic.
Do not rewrite the test from scratch.

Violations:
{problems}

Warnings:
{warnings}
"""
