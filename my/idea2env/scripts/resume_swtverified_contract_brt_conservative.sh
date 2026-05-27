#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for ENV_FILE in "$ROOT_DIR/scripts/.env" "$ROOT_DIR/../scripts/.env"; do
  if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
    break
  fi
done

export CONTRACT_BRT_ENABLE="${CONTRACT_BRT_ENABLE:-1}"
export CONTRACT_BRT_ROOT="${CONTRACT_BRT_ROOT:-$ROOT_DIR}"
export CONTRACT_BRT_CONTRACT_DIR="${CONTRACT_BRT_CONTRACT_DIR:-$ROOT_DIR/contracts}"
export CONTRACT_BRT_GENERATED_TEST_DIR="${CONTRACT_BRT_GENERATED_TEST_DIR:-$ROOT_DIR/generated_tests}"
export CONTRACT_BRT_SCAFFOLD_MODE="${CONTRACT_BRT_SCAFFOLD_MODE:-off}"
export CONTRACT_BRT_PROMPT_MODE="${CONTRACT_BRT_PROMPT_MODE:-reactive}"
export CONTRACT_BRT_INCLUDE_SCAFFOLD_IN_PROMPT="${CONTRACT_BRT_INCLUDE_SCAFFOLD_IN_PROMPT:-0}"
export CONTRACT_BRT_STRICTNESS="${CONTRACT_BRT_STRICTNESS:-warn}"
export CONTRACT_BRT_PREFLIGHT_MODE="${CONTRACT_BRT_PREFLIGHT_MODE:-syntax}"
export PYTHONPATH="$ROOT_DIR:$ROOT_DIR/assertflip_contract/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHON_BIN="${PYTHON_BIN:-python3}"

export RUN_TAG="${RUN_TAG:-swt_verified_contract_brt_conservative_full_rerun_w10_eval8}"
export DATASET="${DATASET:-$ROOT_DIR/datasets/SWT_Verified_Agentless_Test_Source_Skeleton.json}"
export RUN_DIR="${RUN_DIR:-$ROOT_DIR/results/assertflip_${RUN_TAG}_run}"
export RESULTS_DIR="${RESULTS_DIR:-$RUN_DIR/results}"
export OUT_TXT="${OUT_TXT:-$RUN_DIR/assertflip_${RUN_TAG}_summary.txt}"
export LIMIT="${LIMIT:-1000000000}"
export WORKERS="${WORKERS:-10}"
export RUN_EVAL="${RUN_EVAL:-1}"

export EVAL_WORKERS="${EVAL_WORKERS:-8}"
export EVAL_TIMEOUT="${EVAL_TIMEOUT:-3600}"
export EVAL_RUN_ID="${EVAL_RUN_ID:-${RUN_TAG}_resume}"
export EVAL_CACHE_LEVEL="${EVAL_CACHE_LEVEL:-env}"
export EVAL_BUILD_MODE="${EVAL_BUILD_MODE:-api}"
export EVAL_FILTER_SWT="${EVAL_FILTER_SWT:-1}"
export GITHUB_PROXY="${GITHUB_PROXY:-https://ghfast.top/}"
export GITHUB_MIRROR="${GITHUB_MIRROR:-$GITHUB_PROXY}"
export DOCKER_PULL_QUIET_TIMEOUT="${DOCKER_PULL_QUIET_TIMEOUT:-600}"
export SWT_REUSE_CONTAINERS="${SWT_REUSE_CONTAINERS:-0}"
export SWT_KEEP_CONTAINERS="${SWT_KEEP_CONTAINERS:-0}"
export REMOVE_IMAGE_AFTER_RUN="${REMOVE_IMAGE_AFTER_RUN:-0}"

export MODEL="${MODEL:-openai/gpt-4o-mini}"
export PHASE="${PHASE:-pass_then_invert}"
export MAX_GENERATION_RETRIES="${MAX_GENERATION_RETRIES:-3}"
export MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
export DOCKER_IMAGE_REGISTRY="${DOCKER_IMAGE_REGISTRY:-docker.1ms.run}"
export DOCKER_IMAGE_REGISTRIES="${DOCKER_IMAGE_REGISTRIES:-$DOCKER_IMAGE_REGISTRY}"
export PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
export APT_MIRROR="${APT_MIRROR:-https://mirrors.tuna.tsinghua.edu.cn}"

export CONTRACT_BRT_CONSERVATIVE_MERGE="${CONTRACT_BRT_CONSERVATIVE_MERGE:-1}"
export CONTRACT_BRT_BASE_PREDS_FILE="${CONTRACT_BRT_BASE_PREDS_FILE:-/root/Baxxhy/BugReproduce/AssertFlip/assertflip_swt_verified_assertflip_bare_w6_eval6_t3600_run/results/preds_swt_verified_assertflip_bare_w6_eval6_t3600_resume2.jsonl}"
export CONTRACT_BRT_CONTRACT_PREDS_FILE="${CONTRACT_BRT_CONTRACT_PREDS_FILE:-$RESULTS_DIR/preds_${RUN_TAG}_contract_only.jsonl}"

LOG_DIR="$ROOT_DIR/logs"
RUN_STARTED_AT="$(date '+%Y%m%d_%H%M%S')"
LOG_FILE="${LOG_FILE:-$LOG_DIR/resume_${RUN_TAG}_${RUN_STARTED_AT}.log}"
RESUME_DATASET="${RESUME_DATASET:-$RUN_DIR/resume_missing_${RUN_STARTED_AT}.json}"
RESUME_STATS="${RESUME_STATS:-$RUN_DIR/resume_missing_${RUN_STARTED_AT}_stats.json}"
mkdir -p "$LOG_DIR" "$RUN_DIR" "$RESULTS_DIR" "$CONTRACT_BRT_CONTRACT_DIR" "$CONTRACT_BRT_GENERATED_TEST_DIR"

if [[ "${CONTRACT_BRT_LOG_ACTIVE:-0}" != "1" ]]; then
  export CONTRACT_BRT_LOG_ACTIVE=1
  exec > >(tee -a "$LOG_FILE") 2>&1
fi

bash "$ROOT_DIR/scripts/prepare_contract_workspace.sh"

echo "========== Contract-BRT 断点续跑 =========="
echo "RUN_TAG=$RUN_TAG"
echo "RUN_DIR=$RUN_DIR"
echo "RESULTS_DIR=$RESULTS_DIR"
echo "DATASET=$DATASET"
echo "RESUME_DATASET=$RESUME_DATASET"
echo "WORKERS=$WORKERS"
echo "RUN_EVAL=$RUN_EVAL"
echo "EVAL_WORKERS=$EVAL_WORKERS"
echo "CONTRACT_BRT_CONSERVATIVE_MERGE=$CONTRACT_BRT_CONSERVATIVE_MERGE"
echo "CONTRACT_BRT_BASE_PREDS_FILE=$CONTRACT_BRT_BASE_PREDS_FILE"
echo "LOG_FILE=$LOG_FILE"
echo "==========================================="

ACTIVE_COUNT="$(
  {
    ps -eo cmd \
      | grep 'run_taxonomy_sample_20.py' \
      | grep -- "$RESULTS_DIR" \
      | grep -v grep \
      || true
  } | wc -l | tr -d ' '
)"
if [[ "$ACTIVE_COUNT" != "0" && "${ALLOW_PARALLEL_RESUME:-0}" != "1" ]]; then
  echo "检测到同一个 RESULTS_DIR 仍有 $ACTIVE_COUNT 个生成进程在跑。"
  echo "为避免重复写入，先不要启动续跑。确认旧进程停止后再运行本脚本。"
  echo "如果你确认要并行强行续跑，设置 ALLOW_PARALLEL_RESUME=1。"
  exit 9
fi

"$PYTHON_BIN" - "$DATASET" "$RESULTS_DIR" "$RESUME_DATASET" "$RESUME_STATS" "$LIMIT" <<'PY'
import json
import sys
from pathlib import Path

dataset_path = Path(sys.argv[1])
results_dir = Path(sys.argv[2])
resume_dataset_path = Path(sys.argv[3])
stats_path = Path(sys.argv[4])
limit = int(sys.argv[5])

dataset = json.loads(dataset_path.read_text())
selected = dataset[:limit] if limit > 0 and limit < len(dataset) else dataset

completed = []
missing = []
corrupt = []
for item in selected:
    instance_id = item["instance_id"]
    attempts_path = results_dir / f"attempts_{instance_id}.json"
    ok = False
    if attempts_path.exists() and attempts_path.stat().st_size > 0:
        try:
            data = json.loads(attempts_path.read_text(errors="ignore"))
            ok = bool(data)
        except Exception:
            corrupt.append(instance_id)
    if ok:
        completed.append(instance_id)
    else:
        missing.append(item)

resume_dataset_path.parent.mkdir(parents=True, exist_ok=True)
resume_dataset_path.write_text(json.dumps(missing, indent=2) + "\n")
stats = {
    "dataset": str(dataset_path),
    "results_dir": str(results_dir),
    "resume_dataset": str(resume_dataset_path),
    "selected_total": len(selected),
    "completed_attempts": len(completed),
    "missing": len(missing),
    "corrupt_attempts": corrupt,
    "missing_instance_ids": [item["instance_id"] for item in missing],
}
stats_path.write_text(json.dumps(stats, indent=2) + "\n")
print(f"selected_total={len(selected)}")
print(f"completed_attempts={len(completed)}")
print(f"missing={len(missing)}")
print(f"corrupt_attempts={len(corrupt)}")
if missing:
    print("next_missing_head=" + ",".join(item["instance_id"] for item in missing[:10]))
PY

MISSING_COUNT="$("$PYTHON_BIN" - "$RESUME_STATS" <<'PY'
import json, sys
print(json.loads(open(sys.argv[1]).read())["missing"])
PY
)"

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo "DRY_RUN=1，只生成 resume dataset，不启动续跑。"
  exit 0
fi

if [[ "$MISSING_COUNT" != "0" ]]; then
  echo "开始续跑缺失实例: $MISSING_COUNT"
  cd "$ROOT_DIR/scripts"
  "$PYTHON_BIN" run_taxonomy_sample_20.py \
    --limit "$MISSING_COUNT" \
    --dataset "$RESUME_DATASET" \
    --results-dir "$RESULTS_DIR" \
    --model "$MODEL" \
    --phase "$PHASE" \
    --workers "$WORKERS" \
    --max-generation-retries "$MAX_GENERATION_RETRIES" \
    --max-attempts "$MAX_ATTEMPTS"
else
  echo "没有缺失实例，跳过生成阶段。"
fi

cd "$ROOT_DIR"
echo "生成完整数据集视角的本地汇总: $OUT_TXT"
"$PYTHON_BIN" scripts/summarize_assertflip_full.py \
  --dataset "$DATASET" \
  --results-dir "$RESULTS_DIR" \
  --eval-json "${EVAL_JSON:-$ROOT_DIR/results/evaluation_results_on_SWT_Bench/assertFlip_default_run.json}" \
  --out-txt "$OUT_TXT" \
  --limit "$LIMIT"

PREDS_FILE="${PREDS_FILE:-$RESULTS_DIR/preds_${RUN_TAG}.jsonl}"
MODEL_NAME_FOR_EVAL="${MODEL_NAME_FOR_EVAL:-ContractBRTLocal_${RUN_TAG}}"
SWT_BENCH_DIR="${SWT_BENCH_DIR:-$ROOT_DIR/upstream/swt-bench}"

if [[ "$RUN_EVAL" == "1" ]]; then
  echo "开始续跑后的 SWT-Bench 最终验证"
  RESULTS_DIR="$RESULTS_DIR" \
  RUN_TAG="$RUN_TAG" \
  MODEL_NAME_FOR_EVAL="$MODEL_NAME_FOR_EVAL" \
  PREDS_FILE="$PREDS_FILE" \
  SWT_BENCH_DIR="$SWT_BENCH_DIR" \
  EVAL_WORKERS="$EVAL_WORKERS" \
  EVAL_TIMEOUT="$EVAL_TIMEOUT" \
  EVAL_RUN_ID="$EVAL_RUN_ID" \
  EVAL_CACHE_LEVEL="$EVAL_CACHE_LEVEL" \
  EVAL_BUILD_MODE="$EVAL_BUILD_MODE" \
  EVAL_FILTER_SWT="$EVAL_FILTER_SWT" \
  GITHUB_PROXY="$GITHUB_PROXY" \
  GITHUB_MIRROR="$GITHUB_MIRROR" \
  CONTRACT_BRT_CONSERVATIVE_MERGE="$CONTRACT_BRT_CONSERVATIVE_MERGE" \
  CONTRACT_BRT_BASE_PREDS_FILE="$CONTRACT_BRT_BASE_PREDS_FILE" \
  CONTRACT_BRT_CONTRACT_PREDS_FILE="$CONTRACT_BRT_CONTRACT_PREDS_FILE" \
  DATASET="$DATASET" \
  bash "$ROOT_DIR/scripts/run_swtbench_eval_for_results.sh"
else
  echo "RUN_EVAL=0，跳过 SWT-Bench 最终验证，只生成 predictions。"
  "$PYTHON_BIN" "$ROOT_DIR/scripts/generate_preds_phases.py" \
    --results-dir "$RESULTS_DIR" \
    --out-file "$PREDS_FILE" \
    --model-name "$MODEL_NAME_FOR_EVAL"
fi

echo "========== 续跑完成 =========="
echo "resume stats: $RESUME_STATS"
echo "summary: $OUT_TXT"
echo "preds: $PREDS_FILE"
echo "log: $LOG_FILE"
