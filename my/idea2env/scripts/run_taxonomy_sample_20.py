import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

import run_parallel as rp


def progress_prefix(index: int, total: int, instance_id: str) -> str:
    return f"[当前项目 {index}/{total}] {instance_id}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--dataset",
        default="../datasets/SWT_Verified_Agentless_Test_Source_Skeleton.json",
    )
    parser.add_argument("--results-dir", default="../taxonomy_run_20/results")
    parser.add_argument("--model", default="openai/gpt-4o-mini")
    parser.add_argument("--phase", default="pass_then_invert")
    parser.add_argument("--workers", type=int, default=int(os.getenv("WORKERS", "1")))
    parser.add_argument(
        "--max-generation-retries",
        type=int,
        default=int(os.getenv("MAX_GENERATION_RETRIES", "3")),
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=int(os.getenv("MAX_ATTEMPTS", "3")),
    )
    args = parser.parse_args()

    load_dotenv()

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    rp.RESULTS_DIR = str(results_dir)
    rp.ASSERTFLIP_DIR = str((Path(__file__).resolve().parents[1] / "assertflip_contract").resolve())
    rp.model = args.model
    rp.phase_mode = args.phase
    rp.max_generation_retries = args.max_generation_retries
    rp.max_attempts = args.max_attempts

    with open(args.dataset) as f:
        dataset = json.load(f)

    selected = dataset[: args.limit]
    summary_path = results_dir / "run_summary.jsonl"

    print(f"准备运行 AssertFlip，共 {len(selected)} 条数据")
    print(f"模型: {rp.model}")
    print(f"流程: {rp.phase_mode}")
    print(f"并行 workers: {args.workers}")
    print(f"单阶段生成重试 max_generation_retries: {rp.max_generation_retries}")
    print(f"整体尝试轮数 max_attempts: {rp.max_attempts}")
    print(f"结果目录: {results_dir.resolve()}")

    if args.workers <= 1:
        for index, instance in enumerate(selected, start=1):
            instance_id = instance["instance_id"]
            print(f"\n{progress_prefix(index, len(selected), instance_id)} 开始处理")
            result = rp.process_instance(instance)
            result["index"] = index
            with summary_path.open("a") as out:
                out.write(json.dumps(result) + "\n")
            print(f"{progress_prefix(index, len(selected), instance_id)} 处理完成: {result}")
    else:
        indexed_instances = [(index, instance) for index, instance in enumerate(selected, start=1)]
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(rp.process_instance, instance): (index, instance["instance_id"])
                for index, instance in indexed_instances
            }
            print(f"已提交 {len(indexed_instances)} 个项目到并行队列")
            for future in as_completed(futures):
                index, instance_id = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {
                        "instance_id": instance_id,
                        "status": "error",
                        "error": repr(exc),
                    }
                result["index"] = index
                with summary_path.open("a") as out:
                    out.write(json.dumps(result) + "\n")
                print(f"{progress_prefix(index, len(selected), instance_id)} 处理完成: {result}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
