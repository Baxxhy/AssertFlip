import os
import re
from pathlib import Path
from typing import Any


def _issue_keywords(problem_statement: str, limit: int = 12) -> list[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", problem_statement)
    stop = {
        "this", "that", "with", "from", "when", "then", "should", "would",
        "there", "where", "which", "have", "does", "into", "issue",
        "error", "bug", "test", "expected", "actual",
    }
    seen = []
    for word in words:
        lowered = word.lower()
        if lowered in stop or lowered in seen:
            continue
        seen.append(lowered)
        if len(seen) >= limit:
            break
    return seen


def _scan_repo_for_callers(repo_root: Path, function_name: str, max_hits: int = 30) -> list[dict[str, Any]]:
    if not function_name:
        return []
    pattern = re.compile(rf"\b{re.escape(function_name)}\s*\(")
    hits = []
    skip_dirs = {".git", ".tox", ".venv", "venv", "__pycache__", "btcr_results"}
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for filename in files:
            if not filename.endswith(".py"):
                continue
            path = Path(root) / filename
            try:
                lines = path.read_text(errors="ignore").splitlines()
            except Exception:
                continue
            rel = path.relative_to(repo_root).as_posix()
            for lineno, line in enumerate(lines, start=1):
                if pattern.search(line):
                    hits.append({"file": rel, "line": lineno, "code": line.strip()})
                    if len(hits) >= max_hits:
                        return hits
    return hits


def _related_test_evidence(related_tests: list[dict[str, Any]], function_name: str, keywords: list[str]) -> list[str]:
    evidence = []
    for test in related_tests:
        code = test.get("code_content") or test.get("source") or test.get("code") or ""
        name = test.get("name", "<unknown>")
        filename = test.get("file") or test.get("path") or "<unknown>"
        if function_name and re.search(rf"\b{re.escape(function_name)}\b", code):
            evidence.append(f"{filename}::{name} references {function_name}")
        else:
            for keyword in keywords:
                if keyword in code.lower():
                    evidence.append(f"{filename}::{name} contains issue keyword '{keyword}'")
                    break
        if len(evidence) >= 10:
            break
    return evidence


def build_probe_test_plan(environment_contract: dict[str, Any], trigger_contract: dict[str, Any]) -> dict[str, Any]:
    target = trigger_contract.get("target_location", {})
    insert_file = environment_contract.get("insert_file", "")
    hypotheses = trigger_contract.get("trigger_hypotheses", [])
    first_hypothesis = hypotheses[0] if hypotheses else {}
    return {
        "insert_file": insert_file,
        "target_location": target,
        "goal": "Generate a probe test that runs successfully and attempts to execute the target location before adding final F-to-P oracle assertions.",
        "steps": first_hypothesis.get("test_construction_steps", [
            "Reuse imports, fixtures, helpers, and globals from the Environment Contract.",
            "Construct inputs satisfying the Trigger Contract constraints.",
            "Call the highest-confidence public entry API candidate.",
            "Use only lightweight sanity assertions until target-line reachability is validated.",
        ]),
        "coverage_check": f"After the probe runs, check whether {target.get('file', '')}:{target.get('line', '')} was executed.",
    }


def build_trigger_contract(
    *,
    problem_statement: str,
    patch: str,
    target_context: dict[str, Any],
    related_tests: list[dict[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    target = target_context.get("target_location", {})
    function_name = target.get("function", "")
    keywords = _issue_keywords(problem_statement)
    callers = _scan_repo_for_callers(repo_root, function_name)
    related_evidence = _related_test_evidence(related_tests, function_name, keywords)

    candidates = []
    if function_name:
        evidence = [f"Target line is inside function {function_name}."]
        evidence.extend(related_evidence[:3])
        candidates.append({"api": function_name, "confidence": 0.55, "evidence": evidence})
    for hit in callers[:5]:
        candidates.append({
            "api": hit["code"],
            "confidence": 0.35,
            "evidence": [f"{hit['file']}:{hit['line']} calls {function_name}"],
        })

    constraints = []
    for guard in target_context.get("guard_conditions", []):
        constraints.append({
            "type": "branch_condition",
            "constraint": f"Execution must satisfy enclosing guard: {guard}",
            "evidence": f"Guard condition encloses {target.get('file')}:{target.get('line')}.",
        })
    for param in target_context.get("parameters", []):
        constraints.append({
            "type": "input",
            "constraint": f"Provide a value for parameter '{param}' that reaches the target statement.",
            "evidence": f"'{param}' is read by the target statement and is a function parameter.",
        })
    if not constraints:
        constraints.append({
            "type": "input",
            "constraint": "Use issue examples and related test setup to construct inputs that call the target function.",
            "evidence": "No explicit guard or parameter dependency was recovered by the lightweight static analysis.",
        })

    hypotheses = []
    for idx, candidate in enumerate(candidates[:3] or [{"api": function_name or "<entry api>", "evidence": related_evidence[:3]}], start=1):
        hypotheses.append({
            "hypothesis": f"Use {candidate['api']} as the entry point and construct the issue scenario around the localized statement.",
            "test_construction_steps": [
                "Start from the most similar related test file and reuse its imports/setup.",
                "Create the input/object state described by the issue report.",
                f"Call {candidate['api']} so execution enters {function_name or 'the localized function'}.",
                "Use a lightweight sanity assertion first; add the final bug oracle after the probe reaches the target line.",
            ],
            "why_it_should_reach_target_line": "The entry point is tied to the localized function or appears in related tests/call sites.",
            "evidence": candidate.get("evidence", []),
        })

    return {
        "target_location": target,
        "entry_api_candidates": candidates[:8],
        "trigger_constraints": constraints,
        "trigger_hypotheses": hypotheses[:3],
        "observation_state_candidates": [
            {
                "state": "Observe the return value, raised exception, warning, or mutated object state described in the issue.",
                "evidence": "This is the stable observation boundary used before converting the probe into the final BRT oracle.",
            }
        ],
        "static_analysis": {
            "guard_conditions": target_context.get("guard_conditions", []),
            "variables": target_context.get("variables", []),
            "variable_definitions": target_context.get("variable_definitions", {}),
            "callers": callers[:30],
            "related_test_evidence": related_evidence,
            "issue_keywords": keywords,
            "patch_present": bool(patch),
        },
    }
