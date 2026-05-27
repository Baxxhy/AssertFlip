#!/usr/bin/env python3
import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_json(path: Path):
    if not path or not path.exists():
        return None
    return json.loads(path.read_text())


def load_dataset(path: Path):
    data = load_json(path)
    return data or []


def load_run_summary(path: Path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_preds(path: Path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def attempt_has_final_success(path: Path) -> bool:
    try:
        attempts = json.loads(path.read_text())
    except Exception:
        return False
    for item in reversed(attempts):
        if item.get("phase") == "terminating" and item.get("outcome") == "success" and item.get("final_test"):
            return True
    return False


def pct(num, den):
    return round(num / den * 100, 2) if den else 0.0


def write_csv(path: Path, rows):
    columns = ["instance_id", "repo", "generation_status", "accepted", "eval_status", "source"]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})


def card(label, value, sub=""):
    return f"""
      <section class="metric">
        <div class="label">{html.escape(label)}</div>
        <div class="value">{html.escape(str(value))}</div>
        <div class="sub">{html.escape(str(sub))}</div>
      </section>
    """


def bar(label, value, total, color):
    width = pct(value, total)
    return f"""
      <div class="bar-row">
        <div class="bar-label"><span>{html.escape(label)}</span><strong>{value}</strong></div>
        <div class="bar-track"><div class="bar-fill" style="width:{width}%; background:{color};"></div></div>
      </div>
    """


def write_html(path: Path, summary, rows):
    total = summary["input_instances"]
    accepted = summary["accepted_predictions"]
    resolved = summary["resolved"]
    unresolved = summary["unresolved"]
    errors = summary["errors"]
    incomplete = summary["incomplete"]
    gen_counts = summary["generation_status_counts"]
    repo_counts = Counter(row["repo"] for row in rows if row.get("accepted"))

    repo_items = "\n".join(
        f"<tr><td>{html.escape(repo)}</td><td>{count}</td></tr>"
        for repo, count in repo_counts.most_common()
    )
    failure_items = "\n".join(
        f"<tr><td>{html.escape(row['instance_id'])}</td><td>{html.escape(row.get('eval_status') or row.get('generation_status') or '')}</td></tr>"
        for row in rows
        if row.get("eval_status") in {"unresolved", "error", "incomplete"} or (not row.get("accepted") and row.get("generation_status") != "success")
    )

    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{html.escape(summary['run_tag'])} SWT-Bench Verified 汇总</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #20242a; background: #f6f7f9; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
    h1 {{ margin: 0 0 6px; font-size: 28px; }}
    .muted {{ color: #68707d; margin: 0 0 22px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 18px 0; }}
    .metric {{ background: white; border: 1px solid #dfe3e8; border-radius: 8px; padding: 14px; }}
    .label {{ color: #667085; font-size: 13px; }}
    .value {{ font-size: 28px; font-weight: 700; margin-top: 6px; }}
    .sub {{ color: #7a828e; font-size: 12px; min-height: 16px; }}
    .panel {{ background: white; border: 1px solid #dfe3e8; border-radius: 8px; padding: 16px; margin-top: 14px; }}
    .bar-row {{ margin: 12px 0; }}
    .bar-label {{ display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 5px; }}
    .bar-track {{ height: 12px; border-radius: 6px; background: #edf0f3; overflow: hidden; }}
    .bar-fill {{ height: 100%; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
    th, td {{ padding: 9px 8px; border-bottom: 1px solid #eceff3; text-align: left; }}
    th {{ color: #586070; background: #fafbfc; }}
    .cols {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 14px; }}
    @media (max-width: 820px) {{ .cols {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
<main>
  <h1>{html.escape(summary['run_tag'])}</h1>
    <p class="muted">SWT-Bench Verified 全量 AssertFlip 运行汇总，F2P 同时给出全量分母和 accepted 分母。</p>
  <div class="grid">
    {card("输入实例", total)}
    {card("AssertFlip Accepted", accepted, f"{pct(accepted, total):.2f}% of full dataset")}
    {card("F2P 全量成功率", f"{pct(resolved, total):.2f}%", f"{resolved}/{total}")}
    {card("F2P Accepted 成功率", f"{pct(resolved, accepted):.2f}%", f"{resolved}/{accepted}")}
    {card("复现失败", unresolved)}
    {card("评测错误", errors)}
    {card("未完成", incomplete)}
  </div>
  <section class="panel">
    <h2>评测结果</h2>
    {bar("resolved", resolved, max(accepted, 1), "#2e7d32")}
    {bar("unresolved", unresolved, max(accepted, 1), "#c62828")}
    {bar("error", errors, max(accepted, 1), "#ef6c00")}
    {bar("incomplete", incomplete, max(accepted, 1), "#6a737d")}
  </section>
  <section class="panel">
    <h2>生成结果</h2>
    {bar("success", gen_counts.get("success", 0), max(total, 1), "#1565c0")}
    {bar("failed/error", total - gen_counts.get("success", 0), max(total, 1), "#8a4b00")}
  </section>
  <div class="cols">
    <section class="panel">
      <h2>Accepted Repo 分布</h2>
      <table><thead><tr><th>Repo</th><th>Count</th></tr></thead><tbody>{repo_items}</tbody></table>
    </section>
    <section class="panel">
      <h2>失败/未完成条目</h2>
      <table><thead><tr><th>Instance</th><th>Status</th></tr></thead><tbody>{failure_items}</tbody></table>
    </section>
  </div>
</main>
</body>
</html>
""",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--preds-file", required=True)
    parser.add_argument("--eval-report-json", default="")
    parser.add_argument("--out-prefix", required=True)
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    results_dir = Path(args.results_dir)
    preds_file = Path(args.preds_file)
    eval_report = load_json(Path(args.eval_report_json)) if args.eval_report_json else None
    out_prefix = Path(args.out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    dataset = load_dataset(dataset_path)
    dataset_ids = [item["instance_id"] for item in dataset]
    dataset_by_id = {item["instance_id"]: item for item in dataset}
    run_summary = {row["instance_id"]: row for row in load_run_summary(results_dir / "run_summary.jsonl")}
    preds = load_preds(preds_file)
    pred_ids = {row["instance_id"] for row in preds}
    accepted_from_attempts = {
        path.name.removeprefix("attempts_").removesuffix(".json")
        for path in results_dir.glob("attempts_*.json")
        if attempt_has_final_success(path)
    }
    accepted_ids = pred_ids or accepted_from_attempts

    resolved_ids = set(eval_report.get("resolved_ids", [])) if eval_report else set()
    unresolved_ids = set(eval_report.get("unresolved_ids", [])) if eval_report else set()
    error_ids = set(eval_report.get("error_ids", [])) if eval_report else set()

    rows = []
    for instance_id in dataset_ids:
        item = dataset_by_id[instance_id]
        repo = item.get("repo", instance_id.split("__")[0].replace("_", "/"))
        gen = run_summary.get(instance_id, {})
        generation_status = gen.get("status", "not_run")
        accepted = instance_id in accepted_ids
        if instance_id in resolved_ids:
            eval_status = "resolved"
        elif instance_id in unresolved_ids:
            eval_status = "unresolved"
        elif instance_id in error_ids:
            eval_status = "error"
        elif accepted and eval_report:
            eval_status = "incomplete"
        elif accepted:
            eval_status = "accepted_not_evaluated"
        else:
            eval_status = ""
        rows.append(
            {
                "instance_id": instance_id,
                "repo": repo,
                "generation_status": generation_status,
                "accepted": accepted,
                "eval_status": eval_status,
                "source": "swtbench_report" if eval_report and accepted else "assertflip",
            }
        )

    gen_counts = Counter(row["generation_status"] for row in rows)
    eval_counts = Counter(row["eval_status"] for row in rows if row["accepted"])
    total = len(dataset_ids)
    accepted = len(accepted_ids)
    resolved = len(resolved_ids)
    unresolved = len(unresolved_ids)
    errors = len(error_ids)
    incomplete = eval_counts.get("incomplete", 0) + eval_counts.get("accepted_not_evaluated", 0)

    summary = {
        "run_tag": args.run_tag,
        "dataset": str(dataset_path),
        "input_instances": total,
        "accepted_predictions": accepted,
        "resolved": resolved,
        "unresolved": unresolved,
        "errors": errors,
        "incomplete": incomplete,
        "accepted_rate": accepted / total if total else 0,
        "resolved_rate_among_accepted": resolved / accepted if accepted else 0,
        "resolved_rate_among_input": resolved / total if total else 0,
        "generation_status_counts": dict(gen_counts),
        "eval_status_counts": dict(eval_counts),
        "eval_report_json": args.eval_report_json,
        "rows": rows,
    }

    json_path = out_prefix.with_suffix(".json")
    csv_path = out_prefix.with_suffix(".csv")
    html_path = out_prefix.with_suffix(".html")
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(csv_path, rows)
    write_html(html_path, summary, rows)

    print(f"JSON: {json_path}")
    print(f"CSV: {csv_path}")
    print(f"HTML: {html_path}")
    print(json.dumps({key: value for key, value in summary.items() if key != "rows"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
