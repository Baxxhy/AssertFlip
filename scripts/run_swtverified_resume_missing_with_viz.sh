#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export BASE_RUN_TAG="${BASE_RUN_TAG:-swt_verified_assertflip_bare_w6_eval6_t3600}"
export RUN_TAG="${RUN_TAG:-${BASE_RUN_TAG}_resume_missing}"
export DATASET_FULL="${DATASET_FULL:-$ROOT_DIR/datasets/SWT_Verified_Agentless_Test_Source_Skeleton.json}"
export BASE_RUN_DIR="${BASE_RUN_DIR:-$ROOT_DIR/assertflip_${BASE_RUN_TAG}_run}"
export RESULTS_DIR="${RESULTS_DIR:-$BASE_RUN_DIR/results}"
export RESUME_MODE="${RESUME_MODE:-missing_attempts_or_errors}"
export RESUME_DATASET="${RESUME_DATASET:-$BASE_RUN_DIR/resume_${RESUME_MODE}_${RUN_TAG}.json}"
export RESUME_IDS_FILE="${RESUME_IDS_FILE:-$BASE_RUN_DIR/resume_${RESUME_MODE}_${RUN_TAG}.ids.txt}"
export OUT_TXT="${OUT_TXT:-$BASE_RUN_DIR/assertflip_${BASE_RUN_TAG}_combined_after_resume_summary.txt}"
export LIMIT="${LIMIT:-1000000000}"
export WORKERS="${WORKERS:-1}"
export MODEL="${MODEL:-openai/gpt-4o-mini}"
export PHASE="${PHASE:-pass_then_invert}"
export MAX_GENERATION_RETRIES="${MAX_GENERATION_RETRIES:-3}"
export MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
export RUN_EVAL="${RUN_EVAL:-1}"

export EVAL_WORKERS="${EVAL_WORKERS:-1}"
export EVAL_TIMEOUT="${EVAL_TIMEOUT:-1800}"
export EVAL_RUN_ID="${EVAL_RUN_ID:-${RUN_TAG}_$(date '+%Y%m%d_%H%M%S')}"
export EVAL_CACHE_LEVEL="${EVAL_CACHE_LEVEL:-env}"
export EVAL_BUILD_MODE="${EVAL_BUILD_MODE:-api}"
export EVAL_FILTER_SWT="${EVAL_FILTER_SWT:-1}"
export GITHUB_PROXY="${GITHUB_PROXY:-https://ghfast.top/}"
export DOCKER_PULL_QUIET_TIMEOUT="${DOCKER_PULL_QUIET_TIMEOUT:-600}"
export SWT_REUSE_CONTAINERS="${SWT_REUSE_CONTAINERS:-0}"
export SWT_KEEP_CONTAINERS="${SWT_KEEP_CONTAINERS:-0}"

export LOG_DIR="${LOG_DIR:-$ROOT_DIR/logs}"
RUN_STARTED_AT="$(date '+%Y%m%d_%H%M%S')"
export LOG_FILE="${LOG_FILE:-$LOG_DIR/run_${RUN_TAG}_${RUN_STARTED_AT}.log}"
mkdir -p "$LOG_DIR" "$RESULTS_DIR" "$BASE_RUN_DIR"

if [[ "${ASSERTFLIP_LOG_ACTIVE:-0}" != "1" ]]; then
  export ASSERTFLIP_LOG_ACTIVE=1
  exec > >(tee -a "$LOG_FILE") 2>&1
fi

echo "========== AssertFlip SWT-Verified 断点续跑 =========="
echo "base run tag: $BASE_RUN_TAG"
echo "resume run tag: $RUN_TAG"
echo "full dataset: $DATASET_FULL"
echo "base run dir: $BASE_RUN_DIR"
echo "combined results dir: $RESULTS_DIR"
echo "resume mode: $RESUME_MODE"
echo "resume dataset: $RESUME_DATASET"
echo "resume ids: $RESUME_IDS_FILE"
echo "combined summary: $OUT_TXT"
echo "workers: $WORKERS"
echo "model: $MODEL"
echo "run eval after resume: $RUN_EVAL"
echo "eval workers: $EVAL_WORKERS"
echo "eval timeout: $EVAL_TIMEOUT"
echo "======================================================"

python "$ROOT_DIR/scripts/make_resume_dataset.py" \
  --dataset "$DATASET_FULL" \
  --results-dir "$RESULTS_DIR" \
  --out-file "$RESUME_DATASET" \
  --ids-file "$RESUME_IDS_FILE" \
  --mode "$RESUME_MODE"

RESUME_COUNT="$(python - "$RESUME_DATASET" <<'PY'
import json
import sys
from pathlib import Path
print(len(json.loads(Path(sys.argv[1]).read_text())))
PY
)"

echo "需要续跑实例数: $RESUME_COUNT"

if [[ "$RESUME_COUNT" != "0" ]]; then
  cd "$ROOT_DIR/scripts"
  python run_taxonomy_sample_20.py \
    --limit "$LIMIT" \
    --dataset "$RESUME_DATASET" \
    --results-dir "$RESULTS_DIR" \
    --model "$MODEL" \
    --phase "$PHASE" \
    --workers "$WORKERS" \
    --max-generation-retries "$MAX_GENERATION_RETRIES" \
    --max-attempts "$MAX_ATTEMPTS"
else
  echo "没有需要续跑的实例，跳过生成阶段。"
fi

cd "$ROOT_DIR"
echo "基于完整数据集重新生成合并汇总: $OUT_TXT"
python "$ROOT_DIR/scripts/summarize_assertflip_full.py" \
  --dataset "$DATASET_FULL" \
  --results-dir "$RESULTS_DIR" \
  --eval-json "" \
  --out-txt "$OUT_TXT" \
  --limit "$LIMIT"

PREDS_FILE="${PREDS_FILE:-$RESULTS_DIR/preds_${RUN_TAG}.jsonl}"
MODEL_NAME_FOR_EVAL="${MODEL_NAME_FOR_EVAL:-AssertFlipLocal_${RUN_TAG}}"
SWT_BENCH_DIR="${SWT_BENCH_DIR:-/root/Baxxhy/BugReproduce/swt-bench}"

if [[ "$RUN_EVAL" == "1" ]]; then
  echo "基于合并后的全部 attempts 重新生成 preds 并运行 SWT-Bench 评估"
  DATASET="$DATASET_FULL" \
  RESULTS_DIR="$RESULTS_DIR" \
  RUN_TAG="$RUN_TAG" \
  PREDS_FILE="$PREDS_FILE" \
  MODEL_NAME_FOR_EVAL="$MODEL_NAME_FOR_EVAL" \
  SWT_BENCH_DIR="$SWT_BENCH_DIR" \
  EVAL_RUN_ID="$EVAL_RUN_ID" \
  EVAL_WORKERS="$EVAL_WORKERS" \
  EVAL_TIMEOUT="$EVAL_TIMEOUT" \
  EVAL_CACHE_LEVEL="$EVAL_CACHE_LEVEL" \
  EVAL_BUILD_MODE="$EVAL_BUILD_MODE" \
  EVAL_FILTER_SWT="$EVAL_FILTER_SWT" \
  GITHUB_PROXY="$GITHUB_PROXY" \
  "$ROOT_DIR/scripts/run_swtbench_eval_for_results.sh"
fi

LOCAL_REPORT_JSON="$BASE_RUN_DIR/swtbench_eval_${EVAL_RUN_ID}.json"
SWT_REPORT_JSON="$SWT_BENCH_DIR/evaluation_results/${MODEL_NAME_FOR_EVAL}.${EVAL_RUN_ID}.json"
REPORT_FOR_VIS=""
if [[ -f "$LOCAL_REPORT_JSON" ]]; then
  REPORT_FOR_VIS="$LOCAL_REPORT_JSON"
elif [[ -f "$SWT_REPORT_JSON" ]]; then
  REPORT_FOR_VIS="$SWT_REPORT_JSON"
fi

VIS_PREFIX="$BASE_RUN_DIR/final_visual_summary_${RUN_TAG}"
VIS_ARGS=(
  --run-tag "$RUN_TAG"
  --dataset "$DATASET_FULL"
  --results-dir "$RESULTS_DIR"
  --preds-file "$PREDS_FILE"
  --out-prefix "$VIS_PREFIX"
)
if [[ -n "$REPORT_FOR_VIS" ]]; then
  VIS_ARGS+=(--eval-report-json "$REPORT_FOR_VIS")
else
  echo "警告: 没找到 SWT-Bench 评测报告，将只生成 AssertFlip accepted 视角的可视化。"
fi

python "$ROOT_DIR/scripts/visualize_swtbench_verified_results.py" "${VIS_ARGS[@]}"

echo "========== 断点续跑输出 =========="
echo "续跑数据集: $RESUME_DATASET"
echo "续跑实例列表: $RESUME_IDS_FILE"
echo "合并结果目录: $RESULTS_DIR"
echo "合并汇总: $OUT_TXT"
echo "Predictions JSONL: $PREDS_FILE"
echo "可视化 HTML: ${VIS_PREFIX}.html"
echo "汇总 JSON: ${VIS_PREFIX}.json"
echo "汇总 CSV: ${VIS_PREFIX}.csv"
if [[ -n "$REPORT_FOR_VIS" ]]; then
  echo "SWT-Bench 评测 JSON: $REPORT_FOR_VIS"
fi
echo "日志文件: $LOG_FILE"
echo "结束时间: $(date '+%F %T %Z')"
