#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_json(path):
    with Path(path).open() as f:
        return json.load(f)


def load_latest_run_summary(results_dir):
    summary_path = Path(results_dir) / "run_summary.jsonl"
    latest = {}
    if not summary_path.exists():
        return latest
    with summary_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            instance_id = item.get("instance_id")
            if instance_id:
                latest[instance_id] = item
    return latest


def should_resume(instance, results_dir, latest_summary, mode):
    instance_id = instance["instance_id"]
    attempt_path = Path(results_dir) / f"attempts_{instance_id}.json"
    test_path = Path(results_dir) / f"test_assertflip_{instance_id}.py"
    runner = latest_summary.get(instance_id, {})

    has_attempt = attempt_path.exists() and attempt_path.stat().st_size > 0
    has_final_test = test_path.exists() and test_path.stat().st_size > 0
    runner_error = runner.get("status") == "error"

    if mode == "missing_attempts":
        return not has_attempt
    if mode == "run_errors":
        return runner_error and not has_final_test
    if mode == "missing_attempts_or_errors":
        return (not has_attempt) or (runner_error and not has_final_test)
    if mode == "not_accepted":
        return not has_final_test
    raise ValueError(f"unknown mode: {mode}")


def main():
    parser = argparse.ArgumentParser(
        description="Build a smaller dataset containing instances that should be resumed."
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--out-file", required=True)
    parser.add_argument(
        "--mode",
        choices=[
            "missing_attempts",
            "run_errors",
            "missing_attempts_or_errors",
            "not_accepted",
        ],
        default="missing_attempts_or_errors",
        help=(
            "missing_attempts_or_errors is safest for quota-interrupted runs: "
            "it reruns instances with no attempts log or a runner error and no final test."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional limit applied after filtering.",
    )
    parser.add_argument(
        "--ids-file",
        default="",
        help="Optional path to write selected instance IDs, one per line.",
    )
    args = parser.parse_args()

    dataset = load_json(args.dataset)
    results_dir = Path(args.results_dir)
    latest_summary = load_latest_run_summary(results_dir)

    selected = [
        item
        for item in dataset
        if should_resume(item, results_dir, latest_summary, args.mode)
    ]
    if args.limit and args.limit > 0:
        selected = selected[: args.limit]

    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(selected, indent=2) + "\n")

    if args.ids_file:
        ids_path = Path(args.ids_file)
        ids_path.parent.mkdir(parents=True, exist_ok=True)
        ids_path.write_text("\n".join(item["instance_id"] for item in selected) + "\n")

    print(f"selected {len(selected)} instances")
    print(f"dataset: {out_file}")
    if args.ids_file:
        print(f"ids: {args.ids_file}")


if __name__ == "__main__":
    main()
