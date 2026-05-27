from __future__ import annotations

import json
import os
import re
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import ContractValidationReport, EnvironmentContractGraph
from .extractor import build_environment_contract_graph
from .scaffold import build_locked_scaffold, build_prompt_prefix, merge_slots
from .validator import validate_code_in_temp, validate_contract


@dataclass
class ContractContext:
    instance_id: str
    graph: EnvironmentContractGraph
    scaffold: str
    prompt_prefix: str
    artifact_dir: Path
    generated_dir: Path


class ContractBRT:
    def __init__(
        self,
        *,
        root: Path | None = None,
        contract_dir: Path | None = None,
        generated_test_dir: Path | None = None,
        strictness: str = "repair",
        scaffold_mode: str | None = None,
    ) -> None:
        self.root = Path(root or os.getenv("CONTRACT_BRT_ROOT", ".")).resolve()
        self.contract_dir = Path(contract_dir or os.getenv("CONTRACT_BRT_CONTRACT_DIR", self.root / "contracts"))
        self.generated_test_dir = Path(
            generated_test_dir or os.getenv("CONTRACT_BRT_GENERATED_TEST_DIR", self.root / "generated_tests")
        )
        self.strictness = strictness
        self.scaffold_mode = (scaffold_mode or os.getenv("CONTRACT_BRT_SCAFFOLD_MODE", "off")).strip().lower()
        self.prompt_mode = os.getenv("CONTRACT_BRT_PROMPT_MODE", "reactive").strip().lower()
        self.include_scaffold_in_prompt = os.getenv("CONTRACT_BRT_INCLUDE_SCAFFOLD_IN_PROMPT", "0") in {
            "1",
            "true",
            "True",
            "yes",
        }

    def _has_test_entrypoint(self, test_code: str) -> bool:
        try:
            tree = ast.parse(test_code)
        except SyntaxError:
            return True
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                return True
            if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                return True
        return False

    def _needs_django_wrapper(self, test_code: str, context: ContractContext) -> bool:
        if context.graph.metadata.get("project_name") != "django":
            return False
        try:
            tree = ast.parse(test_code)
        except SyntaxError:
            return False
        django_bases = {"SimpleTestCase", "TestCase", "TransactionTestCase", "LiveServerTestCase"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_text = getattr(base, "id", "") or getattr(base, "attr", "")
                    if base_text in django_bases:
                        return False
        return True

    def maybe_apply_scaffold(self, test_code: str, context: ContractContext, *, label: str = "candidate") -> tuple[str, str]:
        mode = self.scaffold_mode
        if mode not in {"off", "fallback", "force"}:
            mode = "fallback"
        if mode == "off":
            return test_code, "off"
        if mode == "force":
            return merge_slots(context.scaffold, test_code), "force"
        if label.startswith("invert_") or "_repair_" in label:
            return test_code, "preserve:refinement_or_inversion"
        if not self._has_test_entrypoint(test_code):
            return merge_slots(context.scaffold, test_code), "fallback:no_test_entrypoint"
        if self._needs_django_wrapper(test_code, context):
            return merge_slots(context.scaffold, test_code), "fallback:django_wrapper"
        return test_code, "preserve"

    def build_contract(
        self,
        *,
        instance_id: str,
        repo_root: Path,
        test_dir: str,
        related_tests_path: Path | None,
        issue_text: str,
        localized_files: list[str],
        runner: str = "pytest",
    ) -> ContractContext:
        graph = build_environment_contract_graph(
            instance_id=instance_id,
            repo_root=repo_root,
            test_dir=test_dir,
            related_tests_path=related_tests_path,
            issue_text=issue_text,
            localized_files=localized_files,
            runner=runner,
        )
        graph.metadata["project_name"] = os.getenv("PROJECT_NAME", "")
        scaffold = build_locked_scaffold(graph, instance_id)
        prompt_prefix = build_prompt_prefix(graph)
        artifact_dir = self.contract_dir / instance_id
        generated_dir = self.generated_test_dir / instance_id
        context = ContractContext(instance_id, graph, scaffold, prompt_prefix, artifact_dir, generated_dir)
        self.save_artifacts(context)
        return context

    def augment_generation_prompt(self, messages: list[dict[str, Any]], context: ContractContext) -> list[dict[str, Any]]:
        if not messages:
            return messages
        if self.prompt_mode in {"off", "none", "reactive"}:
            return messages
        augmented = list(messages)
        augmented[-1] = dict(augmented[-1])
        original_content = str(augmented[-1].get("content", ""))
        if self.prompt_mode == "surgical":
            content = (
                original_content
                + "\n\n"
                + "<CONTRACT_BRT_ENV_HINT>\n"
                + "Use the project's existing test runner/import/setup conventions only when needed to avoid mechanical environment failures. "
                + "Do not change the AssertFlip pass-first objective or assertion direction.\n"
                + "</CONTRACT_BRT_ENV_HINT>"
            )
        else:
            content = original_content + "\n\n" + context.prompt_prefix
        if self.include_scaffold_in_prompt:
            content += (
                "\n<OPTIONAL_TEST_SCAFFOLD_FOR_ENVIRONMENT_FALLBACK>\n"
                + context.scaffold
                + "\n</OPTIONAL_TEST_SCAFFOLD_FOR_ENVIRONMENT_FALLBACK>\n"
            )
        augmented[-1]["content"] = content
        return augmented

    def postprocess_generated_test(self, test_code: str, context: ContractContext, *, label: str = "candidate") -> str:
        context.generated_dir.mkdir(parents=True, exist_ok=True)
        (context.generated_dir / f"{label}_original.py").write_text(test_code)
        processed, mode = self.maybe_apply_scaffold(test_code, context, label=label)
        (context.generated_dir / f"{label}.py").write_text(processed)
        (context.generated_dir / f"{label}_postprocess.json").write_text(
            json.dumps({"label": label, "scaffold_mode": self.scaffold_mode, "decision": mode}, indent=2)
        )
        return processed

    def preflight_code(
        self,
        test_code: str,
        *,
        repo_root: Path,
        context: ContractContext,
        test_command: str = "pytest",
        label: str = "preflight",
    ) -> ContractValidationReport:
        context.generated_dir.mkdir(parents=True, exist_ok=True)
        path = context.generated_dir / f"{label}.py"
        path.write_text(test_code)
        report = validate_code_in_temp(
            test_code,
            repo_root=repo_root,
            graph=context.graph,
            scaffold=context.scaffold,
            test_command=test_command,
        )
        report.save(context.artifact_dir / f"{label}_validation_report.json")
        return report

    def preflight(self, test_path: Path, repo_root: Path, context: ContractContext, test_command: str = "pytest") -> ContractValidationReport:
        report = validate_contract(test_path, repo_root, context.graph, context.scaffold, test_command=test_command)
        report.save(context.artifact_dir / "contract_validation_report.json")
        return report

    def save_artifacts(self, context: ContractContext) -> None:
        context.artifact_dir.mkdir(parents=True, exist_ok=True)
        context.generated_dir.mkdir(parents=True, exist_ok=True)
        context.graph.save(context.artifact_dir / "environment_contract_graph.json")
        (context.artifact_dir / "locked_scaffold.py").write_text(context.scaffold)
        (context.artifact_dir / "prompt_prefix.txt").write_text(context.prompt_prefix)
        metadata = {
            "instance_id": context.instance_id,
            "artifact_dir": str(context.artifact_dir),
            "generated_dir": str(context.generated_dir),
            "strictness": self.strictness,
            "scaffold_mode": self.scaffold_mode,
            "prompt_mode": self.prompt_mode,
            "include_scaffold_in_prompt": self.include_scaffold_in_prompt,
        }
        (context.artifact_dir / "contract_context.json").write_text(json.dumps(metadata, indent=2))


ENVIRONMENT_FAILURE_PATTERNS = (
    (
        "import",
        re.compile(
            r"("
            r"ModuleNotFoundError:"
            r"|ImportError:\s+Failed to import test module"
            r"|ImportError:\s+cannot import name"
            r"|ImportError:\s+No module named"
            r"|from .* import .*ImportError"
            r"|No module named ['\"][A-Za-z0-9_\.]+['\"]"
            r")",
            re.I,
        ),
    ),
    (
        "fixture",
        re.compile(
            r"("
            r"fixture ['\"]?[A-Za-z_][A-Za-z0-9_]*['\"]? not found"
            r"|available fixtures:"
            r"|FixtureLookupError"
            r"|uses no fixture ['\"]?[A-Za-z_][A-Za-z0-9_]*['\"]?"
            r")",
            re.I | re.S,
        ),
    ),
    (
        "settings",
        re.compile(
            r"("
            r"ImproperlyConfigured"
            r"|AppRegistryNotReady"
            r"|Apps aren't loaded yet"
            r"|Requested setting .* but settings are not configured"
            r"|DJANGO_SETTINGS_MODULE"
            r"|settings\.configure\(\)"
            r"|django\.setup\(\)"
            r"|Model class .* doesn't declare an explicit app_label"
            r"|doesn't declare an explicit app_label"
            r"|No installed app with label"
            r"|KeyError:\s*['\"]test_app['\"]"
            r"|INSTALLED_APPS"
            r")",
            re.I | re.S,
        ),
    ),
    (
        "runner",
        re.compile(
            r"("
            r"collected 0 items"
            r"|Ran 0 tests"
            r"|no tests ran"
            r"|ERROR:\s+file or directory not found:"
            r"|ERROR:\s+not found:"
            r"|unrecognized arguments:"
            r"|ImportError:\s+Failed to import test module"
            r"|unittest\.loader\._FailedTest"
            r")",
            re.I,
        ),
    ),
    (
        "base_class",
        re.compile(
            r"(NameError:\s+name ['\"](SimpleTestCase|TestCase|TransactionTestCase|LiveServerTestCase)['\"] is not defined)",
            re.I,
        ),
    ),
    (
        "mock",
        re.compile(
            r"(Mock object has no attribute|AttributeError:\s+Mock object|autospec|spec_set)",
            re.I,
        ),
    ),
)

NON_ENVIRONMENT_FAILURE_PATTERNS = (
    re.compile(r"LLM 验证拒绝|LLM says failure is unrelated|VALIDATION_FEEDBACK", re.I),
    re.compile(r"AssertionError|Failed:\s+DID NOT RAISE|assert .*\n|E\s+assert", re.I),
    re.compile(r"RuntimeWarning:\s+numpy\.ndarray size changed", re.I),
    re.compile(r"ValueError|TypeError|IndexError|KeyError|AttributeError", re.I),
)


def classify_execution_failure(error_text: str | None) -> str | None:
    text = error_text or ""
    if not text.strip():
        return None
    # Do not turn ordinary semantic/assertion failures into environment repair.
    # The specific environment patterns below may still override broad exception
    # classes such as KeyError when they mention Django app setup.
    for name, pattern in ENVIRONMENT_FAILURE_PATTERNS:
        if pattern.search(text):
            return name
    if any(pattern.search(text) for pattern in NON_ENVIRONMENT_FAILURE_PATTERNS):
        return None
    return None


def _labels(graph: EnvironmentContractGraph, node_type: str, limit: int = 5) -> list[str]:
    labels: list[str] = []
    for node in graph.nodes_by_type(node_type):
        label = node.label or node.id.split(":", 1)[-1]
        if label and label not in labels:
            labels.append(label)
        if len(labels) >= limit:
            break
    return labels


def relevant_environment_hints(error_text: str, graph: EnvironmentContractGraph, *, limit: int = 5) -> list[str]:
    kind = classify_execution_failure(error_text) or "environment"
    hints: list[str] = []

    if kind == "import":
        for label in _labels(graph, "ImportContract", limit):
            hints.append(f"Nearby project tests use import contract: {label}")
    elif kind == "fixture":
        for label in _labels(graph, "FixtureContract", limit):
            hints.append(f"Available/recovered pytest fixture contract: {label}")
    elif kind == "settings":
        for label in _labels(graph, "ConfigContract", limit):
            hints.append(f"Recovered project configuration/setup contract: {label}")
        if graph.metadata.get("project_name") == "django":
            hints.append("Django tests often need django.test SimpleTestCase/TestCase or valid app settings before model/app registry access.")
    elif kind == "base_class":
        for label in _labels(graph, "ClassContract", limit):
            hints.append(f"Nearby tests use base class contract: {label}")
    elif kind == "runner":
        hints.append(f"Use the recovered test runner and target directory: runner={graph.runner}, test_dir={graph.test_dir}")
        for label in _labels(graph, "RunnerContract", limit - 1):
            hints.append(f"Runner/config contract: {label}")

    if not hints:
        hints.append(f"Use the recovered runner/test directory: runner={graph.runner}, test_dir={graph.test_dir}")
        for label in _labels(graph, "ImportContract", max(0, limit - 1)):
            hints.append(f"Nearby project tests use import contract: {label}")
    return hints[:limit]


def make_environment_feedback(error_text: str, graph: EnvironmentContractGraph, test_code: str | None = None) -> str:
    kind = classify_execution_failure(error_text) or "environment"
    hints = relevant_environment_hints(error_text, graph)
    hint_block = "\n".join(f"{idx}. {hint}" for idx, hint in enumerate(hints, start=1))
    test_block = f"\nOriginal test:\n```python\n{test_code[:4000]}\n```\n" if test_code else ""
    return (
        f"\n\nCONTRACT_BRT_REACTIVE_ENV_REPAIR ({kind}):\n"
        "The test appears to fail before reaching the intended bug behavior because of a mechanical environment/setup issue.\n"
        "Make the smallest possible change to make the current test executable in this project.\n"
        "Preserve the original bug-triggering logic and preserve the original assertion intent unless the error is directly caused by missing environment setup.\n"
        "Do not rewrite the test from scratch. Do not add unrelated optional dependencies.\n"
        "Only modify imports, settings/setup, test base class/wrapper, fixture usage, app_label, runner-compatible structure, or mock interface if needed.\n"
        "\nRelevant project environment hints:\n"
        f"{hint_block}\n"
        f"{test_block}"
        "\nExecution error excerpt:\n"
        f"{(error_text or '')[:2000]}\n"
        "\nReturn only the repaired complete Python test file.\n"
    )
