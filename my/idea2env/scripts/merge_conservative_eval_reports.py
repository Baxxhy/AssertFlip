#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def status_map(report: dict[str, Any]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for key, status in (
        ("resolved_ids", "resolved"),
        ("unresolved_ids", "unresolved"),
        ("error_ids", "error"),
    ):
        for instance_id in report.get(key, []) or []:
            statuses[str(instance_id)] = status
    return statuses


def read_jsonl_ids(path: Path) -> list[str]:
    ids: list[str] = []
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            instance_id = row.get("instance_id")
            if instance_id:
                ids.append(str(instance_id))
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a conservative Contract-BRT evaluation report from two completed SWT-Bench reports. "
            "Base AssertFlip statuses win on overlap; Contract-BRT statuses are used only for rescue predictions."
        )
    )
    parser.add_argument("--base-report", required=True)
    parser.add_argument("--contract-report", required=True)
    parser.add_argument("--merged-preds", required=True)
    parser.add_argument("--dataset", default="")
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-txt", required=True)
    args = parser.parse_args()

    base_report = load_json(Path(args.base_report))
    contract_report = load_json(Path(args.contract_report))
    base_status = status_map(base_report)
    contract_status = status_map(contract_report)
    merged_ids = read_jsonl_ids(Path(args.merged_preds))

    resolved_ids: list[str] = []
    unresolved_ids: list[str] = []
    error_ids: list[str] = []
    missing_ids: list[str] = []
    rescue_ids: list[str] = []

    for instance_id in merged_ids:
        if instance_id in base_status:
            status = base_status[instance_id]
        elif instance_id in contract_status:
            status = contract_status[instance_id]
            rescue_ids.append(instance_id)
        else:
            status = "error"
            missing_ids.append(instance_id)

        if status == "resolved":
            resolved_ids.append(instance_id)
        elif status == "unresolved":
            unresolved_ids.append(instance_id)
        else:
            error_ids.append(instance_id)

    full_total = len(merged_ids)
    dataset_path = Path(args.dataset) if args.dataset else None
    if dataset_path and dataset_path.exists():
        try:
            full_total = len(json.loads(dataset_path.read_text()))
        except Exception:
            full_total = len(merged_ids)

    accepted_total = len(merged_ids)
    resolved = len(resolved_ids)
    unresolved = len(unresolved_ids)
    errors = len(error_ids)

    merged_report = {
        "total_instances": accepted_total,
        "completed_instances": 0,
        "resolved_instances": resolved,
        "unresolved_instances": unresolved,
        "error_instances": errors,
        "resolved_ids": resolved_ids,
        "unresolved_ids": unresolved_ids,
        "error_ids": error_ids,
        "contract_rescue_ids": rescue_ids,
        "missing_status_ids": missing_ids,
        "source_reports": {
            "base_report": str(Path(args.base_report)),
            "contract_report": str(Path(args.contract_report)),
            "merged_preds": str(Path(args.merged_preds)),
        },
        "merge_policy": "base AssertFlip status wins; Contract-BRT status is used only for base-missing rescue predictions",
    }

    out_json = Path(args.out_json)
    out_txt = Path(args.out_txt)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_txt.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(merged_report, indent=2) + "\n")

    accepted_rate = (accepted_total / full_total * 100) if full_total else 0.0
    f2p_full = (resolved / full_total * 100) if full_total else 0.0
    f2p_accepted = (resolved / accepted_total * 100) if accepted_total else 0.0
    lines = [
        "Contract-BRT conservative merge derived evaluation",
        f"base report: {args.base_report}",
        f"contract report: {args.contract_report}",
        f"merged preds: {args.merged_preds}",
        f"original dataset size: {full_total}",
        f"accepted / evaluated predictions: {accepted_total}",
        f"resolved F2P: {resolved}",
        f"unresolved: {unresolved}",
        f"errors: {errors}",
        f"contract rescue predictions: {len(rescue_ids)}",
        f"accepted rate: {accepted_rate:.2f}%",
        f"F2P rate over full dataset: {f2p_full:.2f}%",
        f"F2P rate over accepted predictions: {f2p_accepted:.2f}%",
        f"missing status ids: {len(missing_ids)}",
    ]
    out_txt.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
