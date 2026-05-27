#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Merge bare AssertFlip predictions with Contract-BRT rescue predictions. "
            "Bare predictions win for overlapping instance IDs; Contract-BRT is used only for instances "
            "that bare AssertFlip did not already accept."
        )
    )
    parser.add_argument("--base-preds", required=True)
    parser.add_argument("--contract-preds", required=True)
    parser.add_argument("--out-file", required=True)
    parser.add_argument("--model-name", default="")
    args = parser.parse_args()

    base_rows = read_jsonl(Path(args.base_preds))
    contract_rows = read_jsonl(Path(args.contract_preds))
    merged: dict[str, dict] = {}
    source: dict[str, str] = {}

    for row in base_rows:
        instance_id = row.get("instance_id")
        if not instance_id:
            continue
        merged[instance_id] = row
        source[instance_id] = "base"

    for row in contract_rows:
        instance_id = row.get("instance_id")
        if not instance_id or instance_id in merged:
            continue
        merged[instance_id] = row
        source[instance_id] = "contract_rescue"

    if args.model_name:
        for row in merged.values():
            row["model_name_or_path"] = args.model_name

    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w") as handle:
        for instance_id in sorted(merged):
            handle.write(json.dumps(merged[instance_id]) + "\n")

    rescue_count = sum(1 for item in source.values() if item == "contract_rescue")
    print(f"base predictions: {len(base_rows)}")
    print(f"contract predictions: {len(contract_rows)}")
    print(f"merged predictions: {len(merged)}")
    print(f"contract rescue additions: {rescue_count}")
    print(f"wrote: {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
