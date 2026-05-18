import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


TAXONOMY = {
    "Mechanical Failure": {
        "Not Implemented",
        "Output Format Inconsistency",
        "Environment Error",
        "Incorrect File Reference",
        "Wrong API Call",
    },
    "Misimplementation": {
        "Incorrect Input/Mock",
        "Incorrect Assertion",
        "Logical Failure",
    },
    "Requirement Misunderstanding": {
        "Misunderstanding Function Logic From Natural Language",
        "Misunderstanding Edge Case Logic",
    },
}


def project_name(instance_id: str) -> str:
    owner_or_project = instance_id.split("__", 1)[0]
    if owner_or_project in {"django", "astropy", "sympy"}:
        return owner_or_project
    return owner_or_project.replace("-", "_")


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def clean_error(text: str, limit: int = 600) -> str:
    text = ANSI_RE.sub("", text or "")
    text = re.sub(r"\n+", "\n", text).strip()
    if not text:
        return ""

    priority_patterns = [
        r"E\s+([A-Za-z_][\w.]*Error: .+)",
        r"(AssertionError: .+)",
        r"(Failed: .+)",
        r"(No installed app with label .+)",
        r"(ModuleNotFoundError: .+)",
        r"(ImportError: .+)",
        r"(TypeError: .+)",
        r"(ValueError: .+)",
        r"(AttributeError: .+)",
    ]
    for pattern in priority_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()[:limit]

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if any(token in line for token in ("Error", "FAILED", "FAIL", "No installed app", "Traceback")):
            return line[:limit]
    return " ".join(lines[-3:])[:limit]


def terminal_outcome(attempts: list[dict]) -> str:
    for item in reversed(attempts):
        if item.get("phase") == "terminating":
            return item.get("outcome", "unknown")
    return "unknown"


def collect_failure_signal(attempts: list[dict]) -> tuple[str, str, str]:
    """Return phase, concrete reason, and a text blob used for classification."""
    generation_markers = sum(1 for item in attempts if "generation_attempt" in item and item.get("phase") is None)
    generated_first_tests = sum(1 for item in attempts if item.get("phase") == "first_test")
    passing_candidates = [
        item for item in attempts
        if item.get("phase") == "generate_passing_test" and item.get("status") == "passing"
    ]
    failing_passing_tests = [
        item for item in attempts
        if item.get("phase") == "generate_passing_test" and item.get("status") == "failing"
    ]
    inversion_failures = [
        item for item in attempts
        if item.get("phase") == "invert_to_failing" and item.get("status") == "failing"
    ]
    rejected_validations = [
        item for item in attempts
        if item.get("phase") == "validate_bug_with_llm" and str(item.get("revealing")).lower() == "false"
    ]

    if rejected_validations:
        last = rejected_validations[-1]
        reason = clean_error(_text(last.get("reason"))) or "LLM rejected the inverted failing test as not exposing the reported bug."
        error = clean_error(_text(last.get("error")))
        detail = (
            f"Phase A generated {len(passing_candidates)} passing candidate(s), "
            f"but inversion/LLM validation rejected {len(rejected_validations)} failing candidate(s). "
            f"Last validation reason: {reason}"
        )
        if error:
            detail += f" Last pytest failure: {error}"
        blob = "\n".join([detail, _text(last.get("test_code")), _text(last.get("error"))])
        return "validate_bug_with_llm", detail, blob

    if not passing_candidates and failing_passing_tests:
        last = failing_passing_tests[-1]
        error = clean_error(_text(last.get("error"))) or "pytest failed before a passing baseline test was obtained."
        detail = (
            f"Phase A failed before inversion: 0 passing candidate(s); "
            f"{len(failing_passing_tests)} failing execution(s) across "
            f"{generation_markers or generated_first_tests} generation attempt(s). "
            f"Last pytest failure: {error}"
        )
        blob = "\n".join([detail, _text(last.get("test_code")), _text(last.get("error"))])
        return "generate_passing_test", detail, blob

    if inversion_failures:
        last = inversion_failures[-1]
        error = clean_error(_text(last.get("error"))) or "Inverted test failed, but no LLM validation reason was recorded."
        detail = (
            f"Generated {len(passing_candidates)} passing candidate(s), then inversion failed "
            f"{len(inversion_failures)} time(s). Last pytest failure: {error}"
        )
        blob = "\n".join([detail, _text(last.get("test_code")), _text(last.get("error"))])
        return "invert_to_failing", detail, blob

    interesting = []
    for item in attempts:
        if item.get("phase") == "validate_bug_with_llm" and item.get("revealing") is False:
            interesting.append(item)
        elif item.get("status") in {"failing", "error", "failed_to_generate", "no_python_code", "no_response"}:
            interesting.append(item)
        elif item.get("outcome") == "failure":
            interesting.append(item)

    item = interesting[-1] if interesting else attempts[-1]
    phase = _text(item.get("phase", "unknown"))
    reason_parts = [
        _text(item.get("reason")),
        _text(item.get("feedback")),
        _text(item.get("error")),
        _text(item.get("status")),
    ]
    reason = "\n".join(part for part in reason_parts if part).strip()
    blob = "\n".join([reason, _text(item.get("test_code")), _text(item.get("response"))])
    if reason:
        reason = clean_error(reason) or reason
    if not reason:
        reason = "No explicit error or validation reason was recorded."
    return phase, reason, blob


def classify(phase: str, reason: str, blob: str) -> tuple[str, str, str]:
    lower = blob.lower()
    reason_lower = reason.lower()

    if "validate_bug_with_llm" in phase or "last validation reason" in reason_lower:
        if re.search(r"equivalent|scaling factor|unit equivalence|edge case|boundary|empty|corner case", lower):
            return (
                "Requirement Misunderstanding",
                "Misunderstanding Edge Case Logic",
                "The generated test misses an edge-case or equivalence condition required by the reported behavior.",
            )
        if re.search(r"incorrectly assert|incorrectly asserting|wrong assertion|assertion checks|expects?|expected|actual|exception message|checks for", lower):
            return (
                "Misimplementation",
                "Incorrect Assertion",
                "The generated test reaches an oracle but asserts the wrong expected behavior.",
            )
        if re.search(r"does not account|specific conditions|conditions under which|scenario|test setup|input", lower):
            return (
                "Misimplementation",
                "Incorrect Input/Mock",
                "The generated test does not recreate the input/setup conditions needed to trigger the bug.",
            )

    if re.search(r"\b(todo|placeholder|assert false)\b|pass\s*#", lower) or "notimplementederror" in lower:
        return (
            "Mechanical Failure",
            "Not Implemented",
            "The generated test is missing a real implementation or contains placeholder logic.",
        )

    if re.search(r"no python code|failed_to_generate|no_response|unable to extract python", lower):
        return (
            "Mechanical Failure",
            "Not Implemented",
            "The tool did not produce an executable Python test body.",
        )

    if re.search(r"no such file|file .* does not exist|filenotfounderror|incorrect file|path .* not found", lower):
        return (
            "Mechanical Failure",
            "Incorrect File Reference",
            "The test or harness refers to a file path that is not present in the target project.",
        )

    if re.search(r"unrecognized arguments|no coverage data|coverage data file|timeout|timed out|command.*returned non-zero|failed to convert coverage|dependency|environment", lower):
        return (
            "Mechanical Failure",
            "Environment Error",
            "The failure occurs in the execution harness or environment before a meaningful bug oracle is evaluated.",
        )

    if re.search(r"modulenotfounderror|importerror: no module named|cannot import name", lower):
        if "/testbed/" in lower or "from astropy" in lower or "from django" in lower or "from sklearn" in lower:
            return (
                "Mechanical Failure",
                "Wrong API Call",
                "The test imports or calls a project API symbol that is unavailable in this version.",
            )
        return (
            "Mechanical Failure",
            "Environment Error",
            "The test cannot start because a required module is unavailable.",
        )

    if re.search(r"attributeerror|unexpected keyword|missing .* required positional|takes .* positional|typeerror", lower):
        return (
            "Mechanical Failure",
            "Wrong API Call",
            "The test interacts with a library or project API using the wrong signature or symbol.",
        )

    if re.search(r"formatting|formatted string|whitespace|repr|string representation|exception message|message should|actual exception message", lower):
        return (
            "Mechanical Failure",
            "Output Format Inconsistency",
            "The oracle appears to expect a different representation or ordering than the actual output.",
        )

    if re.search(r"no installed app|app_label|settings\.configure|improperlyconfigured|apps aren't loaded|model.*app|mock|monkeypatch|fixture|setup|input|invalid value|keyerror|valueerror|indexerror", lower):
        return (
            "Misimplementation",
            "Incorrect Input/Mock",
            "The test setup, input, mock, or fixture does not recreate the buggy state correctly.",
        )

    if re.search(r"incorrectly asserting|assertionerror|assert |did not raise|not equal|expected|actual|opposite|wrong assertion|oracle", lower):
        return (
            "Misimplementation",
            "Incorrect Assertion",
            "The test reaches an oracle but checks the wrong expected state or wrong variable.",
        )

    if re.search(r"edge case|boundary|empty|shared reference|shallow copy|corner case", lower):
        return (
            "Requirement Misunderstanding",
            "Misunderstanding Edge Case Logic",
            "The failure indicates the test missed an edge-case condition required by the issue.",
        )

    if re.search(r"misunderstood|natural language|issue description|requirement|semantics|domain", lower):
        return (
            "Requirement Misunderstanding",
            "Misunderstanding Function Logic From Natural Language",
            "The failure indicates the issue text was translated into the wrong functional behavior.",
        )

    if "validate_bug_with_llm" in phase or "validation" in reason_lower or "unrelated" in reason_lower:
        return (
            "Misimplementation",
            "Logical Failure",
            "The generated test executes but is semantically disconnected from the reported bug trigger.",
        )

    return (
        "Misimplementation",
        "Logical Failure",
        "The recorded failure does not match a mechanical/runtime pattern and is best explained as incorrect test logic.",
    )


def classify_attempt_file(path: Path) -> dict:
    attempts = json.loads(path.read_text())
    instance_id = attempts[0].get("instance_id", path.stem.removeprefix("attempts_"))
    outcome = terminal_outcome(attempts)

    if outcome == "success":
        return {
            "project_name": project_name(instance_id),
            "instance_id": instance_id,
            "status": "success",
            "taxonomy_class": "Accepted",
            "taxonomy_subclass": "Accepted",
            "phase": "terminating",
            "specific_reason": "AssertFlip accepted a final bug-revealing test for this instance.",
            "classification_rationale": "No failure taxonomy label assigned because this run produced an accepted test.",
        }

    phase, reason, blob = collect_failure_signal(attempts)
    klass, subclass, rationale = classify(phase, reason, blob)
    return {
        "project_name": project_name(instance_id),
        "instance_id": instance_id,
        "status": "failure",
        "taxonomy_class": klass,
        "taxonomy_subclass": subclass,
        "phase": phase,
        "specific_reason": reason,
        "classification_rationale": rationale,
    }


def load_run_summary_errors(results_dir: Path, seen_instance_ids: set[str]) -> list[dict]:
    summary_path = results_dir / "run_summary.jsonl"
    if not summary_path.exists():
        return []

    rows = []
    for line in summary_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        instance_id = item.get("instance_id", "")
        if not instance_id or instance_id in seen_instance_ids:
            continue
        if item.get("status") != "error":
            continue
        reason = item.get("error") or "Runner reported an error without a detailed message."
        klass, subclass, rationale = classify("runner", reason, reason)
        rows.append({
            "project_name": project_name(instance_id),
            "instance_id": instance_id,
            "status": "failure",
            "taxonomy_class": klass,
            "taxonomy_subclass": subclass,
            "phase": "runner",
            "specific_reason": reason,
            "classification_rationale": rationale,
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="../taxonomy_run_20/results")
    parser.add_argument("--out-dir", default="../taxonomy_run_20/classification")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = [classify_attempt_file(path) for path in sorted(results_dir.glob("attempts_*.json"))]
    seen_instance_ids = {row["instance_id"] for row in rows}
    rows.extend(load_run_summary_errors(results_dir, seen_instance_ids))

    json_path = out_dir / "taxonomy_classification.json"
    csv_path = out_dir / "taxonomy_classification.csv"
    summary_path = out_dir / "taxonomy_summary.md"

    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False))

    fieldnames = [
        "project_name",
        "instance_id",
        "status",
        "taxonomy_class",
        "taxonomy_subclass",
        "phase",
        "specific_reason",
        "classification_rationale",
    ]
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    by_class = Counter(row["taxonomy_class"] for row in rows)
    by_subclass = Counter((row["taxonomy_class"], row["taxonomy_subclass"]) for row in rows)
    failed_rows = [row for row in rows if row["status"] == "failure"]

    lines = [
        "# AssertFlip Taxonomy Classification",
        "",
        f"Total classified attempts: {len(rows)}",
        f"Accepted by AssertFlip: {sum(row['status'] == 'success' for row in rows)}",
        f"Failed before acceptance: {len(failed_rows)}",
        "",
        "## By Class",
    ]
    for key, count in by_class.most_common():
        lines.append(f"- {key}: {count}")

    lines.extend(["", "## By Subclass"])
    for (klass, subclass), count in by_subclass.most_common():
        lines.append(f"- {klass} / {subclass}: {count}")

    lines.extend(["", "## Failed Instance Details"])
    for row in failed_rows:
        reason = row["specific_reason"].replace("\n", " ")
        if len(reason) > 500:
            reason = reason[:497] + "..."
        lines.append(
            f"- {row['project_name']} / {row['instance_id']}: {row['taxonomy_class']} / {row['taxonomy_subclass']} "
            f"({row['phase']}) - {reason}"
        )

    summary_path.write_text("\n".join(lines) + "\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
