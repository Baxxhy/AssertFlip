import argparse
import json
import re
from pathlib import Path


def load_json(path: Path, default):
    if not path or not path.exists():
        return default
    with path.open() as f:
        return json.load(f)


def load_run_summary(results_dir: Path):
    summary = {}
    path = results_dir / "run_summary.jsonl"
    if not path.exists():
        return summary
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            instance_id = item.get("instance_id")
            if instance_id:
                summary[instance_id] = item
    return summary


def clean_text(text, limit=500):
    if text is None:
        return ""
    text = re.sub(r"\x1b\[[0-9;]*m", "", str(text))
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def zh_yes_no(value):
    return {"yes": "是", "no": "否"}.get(value, value)


def zh_f2p_status(value):
    return {
        "success": "成功",
        "failure": "失败",
        "error": "运行错误",
        "not_evaluated": "作者评测无结果",
        "no_eval_json": "没有评测JSON",
    }.get(value, value)


def local_result(summary, runner):
    if runner.get("status") == "error":
        return "运行错误"
    if summary["accepted_by_assertflip"] == "yes":
        return "本地生成成功，AssertFlip已接受"
    if summary["generated"] == "yes":
        return "本地生成了尝试，但AssertFlip未接受"
    if runner.get("status") == "success":
        return "本地运行完成，但没有找到生成日志"
    return "没有生成日志"


def zh_phase(value):
    return {
        "passing_first": "先生成通过测试再反转",
        "direct_fail": "直接生成失败测试",
    }.get(value, value)


def zh_error(text):
    if not text:
        return ""
    replacements = [
        ("empty or unreadable attempt log", "尝试日志为空或无法读取"),
        ("LLM validation rejected:", "LLM 验证拒绝："),
        (
            "AssertFlip terminated without success",
            "AssertFlip 结束但没有成功生成可用测试",
        ),
        (
            "AssertFlip did not reach a successful terminating record",
            "AssertFlip 没有走到成功结束记录",
        ),
        (
            "SWT-Bench evaluation marked unresolved; aggregate eval JSON has no per-test traceback",
            "SWT-Bench 评测标记为未解决；汇总评测 JSON 没有这一条的详细 traceback",
        ),
        (
            "not present in the supplied SWT-Bench evaluation JSON",
            "这条数据不在当前提供的 SWT-Bench 评测 JSON 中",
        ),
        ("no attempt log found", "没有找到 attempts 日志"),
        ("skipped by runner", "被运行脚本跳过"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def last_matching(items, predicate):
    for item in reversed(items):
        if predicate(item):
            return item
    return None


def attempt_summary(path: Path):
    attempts = load_json(path, [])
    if not attempts:
        return {
            "generated": "no",
            "accepted_by_assertflip": "no",
            "phase": "",
            "run_coverage_percent": "",
            "error": "empty or unreadable attempt log",
        }

    terminating = last_matching(
        attempts,
        lambda x: x.get("phase") == "terminating",
    )
    accepted = bool(terminating and terminating.get("outcome") == "success")
    phase = terminating.get("mode", "") if terminating else ""

    cov_item = last_matching(
        attempts,
        lambda x: isinstance(x.get("coverage"), dict)
        and "percent_covered" in x.get("coverage", {}),
    )
    run_cov = ""
    if cov_item:
        run_cov = f"{cov_item['coverage']['percent_covered']:.2f}"

    error = ""
    if not accepted:
        validation = last_matching(
            attempts,
            lambda x: x.get("phase") == "validate_bug_with_llm"
            and x.get("revealing") is False,
        )
        errored = last_matching(
            attempts,
            lambda x: x.get("error")
            and x.get("phase") in {
                "generate_passing_test",
                "generate_failing_test",
                "invert_to_failing",
                "runner",
            },
        )
        failed = last_matching(
            attempts,
            lambda x: x.get("phase") == "invert_to_failing"
            and x.get("outcome") == "failure",
        )
        if validation:
            error = "LLM validation rejected: " + clean_text(validation.get("reason"))
        elif errored:
            error = clean_text(errored.get("error"))
        elif failed:
            error = clean_text(failed.get("reason"))
        elif terminating:
            error = clean_text(terminating.get("outcome", "AssertFlip terminated without success"))
        else:
            error = "AssertFlip did not reach a successful terminating record"

    return {
        "generated": "yes",
        "accepted_by_assertflip": "yes" if accepted else "no",
        "phase": phase,
        "run_coverage_percent": run_cov,
        "error": error,
    }


def eval_sets(eval_json: Path):
    data = load_json(eval_json, {})
    resolved = set(data.get("resolved_ids", []))
    unresolved = set(data.get("unresolved_ids", []))
    errors = set(data.get("error_ids", []))
    evaluated = resolved | unresolved | errors
    return data, resolved, unresolved, errors, evaluated


def f2p_status(instance_id, resolved, unresolved, errors, evaluated):
    if instance_id in resolved:
        return "success"
    if instance_id in unresolved:
        return "failure"
    if instance_id in errors:
        return "error"
    if evaluated:
        return "not_evaluated"
    return "no_eval_json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--eval-json", default="")
    parser.add_argument("--out-txt", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    dataset_path = Path(args.dataset).resolve()
    results_dir = Path(args.results_dir).resolve()
    eval_json = Path(args.eval_json).resolve() if args.eval_json else None
    out_txt = Path(args.out_txt).resolve()
    out_txt.parent.mkdir(parents=True, exist_ok=True)

    full_dataset = load_json(dataset_path, [])
    dataset = full_dataset[: args.limit] if args.limit and args.limit > 0 else full_dataset
    run_summary = load_run_summary(results_dir)

    rows = []
    for index, instance in enumerate(dataset, start=1):
        instance_id = instance["instance_id"]
        attempt_path = results_dir / f"attempts_{instance_id}.json"
        summary = attempt_summary(attempt_path) if attempt_path.exists() else {
            "generated": "no",
            "accepted_by_assertflip": "no",
            "phase": "",
            "run_coverage_percent": "",
            "error": "",
        }
        runner = run_summary.get(instance_id, {})
        if runner.get("status") == "error":
            summary["error"] = clean_text(runner.get("error"))
        elif not attempt_path.exists() and runner.get("status") == "skipped":
            summary["error"] = clean_text(runner.get("error") or "skipped by runner")
        elif not attempt_path.exists():
            summary["error"] = "no attempt log found"

        rows.append({
            "index": index,
            "instance_id": instance_id,
            "local_result": local_result(summary, runner),
            **summary,
        })

    total = len(dataset)
    generated_count = sum(1 for r in rows if r["generated"] == "yes")
    accepted_count = sum(1 for r in rows if r["accepted_by_assertflip"] == "yes")
    runner_error_count = sum(1 for r in rows if r["local_result"] == "运行错误")
    unaccepted_count = sum(
        1 for r in rows
        if r["local_result"] == "本地生成了尝试，但AssertFlip未接受"
    )
    accepted_rate = (accepted_count / total * 100) if total else 0.0

    lines = [
        "AssertFlip 运行汇总报告",
        f"数据集文件: {dataset_path}",
        f"本报告统计范围: 前 {len(dataset)} 条 / 数据集原始总数 {len(full_dataset)} 条",
        f"结果目录: {results_dir}",
        "",
        "指标说明:",
        "- 这个报告只统计你这次本地运行 AssertFlip 的结果，不再混入仓库自带的历史评测 JSON。",
        "- “本地生成成功，AssertFlip已接受”表示 AssertFlip 生成并接受了一个 bug-revealing 测试文件。",
        "- 这还不是最终 F2P。真正 F2P 还需要再跑 SWE-Bench evaluator：测试要在 buggy 版本失败，并且在 fixed/golden patch 版本通过。",
        "- 论文里的覆盖率是 Delta Mean Change Coverage，也就是 golden patch 修改行上的覆盖率变化；不是 attempts 日志里的普通 coverage.py 总覆盖率。",
        "- 当前表里的运行覆盖率来自 attempts 日志，是生成测试在 buggy checkout 上跑出来的普通 coverage.py 总覆盖率。",
        "",
        f"总条数: {total}",
        f"有生成尝试日志的条数: {generated_count}",
        f"被 AssertFlip 在 buggy 侧接受的条数: {accepted_count}",
        f"本地接受率: {accepted_rate:.2f}%",
        f"生成了尝试但未被接受的条数: {unaccepted_count}",
        f"本地运行错误条数: {runner_error_count}",
        "最终 F2P 成功条数: 当前未计算，需要另跑 SWE-Bench evaluator",
        "最终 F2P 成功率: 当前未计算，需要另跑 SWE-Bench evaluator",
    ]

    lines.extend([
        "",
        "逐条结果表:",
        "序号\t实例ID\t本地运行结果\t是否有生成日志\t是否被AssertFlip接受\t流程阶段\t运行覆盖率百分比\t失败原因或说明",
    ])
    for row in rows:
        lines.append("\t".join([
            str(row["index"]),
            str(row["instance_id"]),
            str(row["local_result"]),
            zh_yes_no(str(row["generated"])),
            zh_yes_no(str(row["accepted_by_assertflip"])),
            zh_phase(str(row["phase"])),
            str(row["run_coverage_percent"]),
            zh_error(str(row["error"])),
        ]))

    out_txt.write_text("\n".join(lines) + "\n")
    print(f"已写入汇总报告: {out_txt}")


if __name__ == "__main__":
    main()
