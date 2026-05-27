#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export RUN_TAG="${RUN_TAG:-swt_verified_full}"
export DATASET="${DATASET:-$ROOT_DIR/datasets/SWT_Verified_Agentless_Test_Source_Skeleton.json}"
export RUN_DIR="${RUN_DIR:-$ROOT_DIR/assertflip_${RUN_TAG}_run}"
export RESULTS_DIR="${RESULTS_DIR:-$RUN_DIR/results}"
export OUT_TXT="${OUT_TXT:-$RUN_DIR/assertflip_${RUN_TAG}_summary.txt}"
export EVAL_JSON="${EVAL_JSON:-$ROOT_DIR/evaluation_results_on_SWT_Bench/assertFlip_default_run.json}"
export LIMIT="${LIMIT:-1000000000}"
export WORKERS="${WORKERS:-1}"
export RUN_EVAL="${RUN_EVAL:-1}"

export EVAL_WORKERS="${EVAL_WORKERS:-1}"
export EVAL_TIMEOUT="${EVAL_TIMEOUT:-1800}"
export EVAL_RUN_ID="${EVAL_RUN_ID:-${RUN_TAG}_$(date '+%Y%m%d_%H%M%S')}"
export EVAL_CACHE_LEVEL="${EVAL_CACHE_LEVEL:-instance}"
export EVAL_BUILD_MODE="${EVAL_BUILD_MODE:-api}"
export EVAL_FILTER_SWT="${EVAL_FILTER_SWT:-1}"
export GITHUB_PROXY="${GITHUB_PROXY:-https://ghfast.top/}"
export DOCKER_PULL_QUIET_TIMEOUT="${DOCKER_PULL_QUIET_TIMEOUT:-600}"
export SWT_REUSE_CONTAINERS="${SWT_REUSE_CONTAINERS:-1}"
export SWT_KEEP_CONTAINERS="${SWT_KEEP_CONTAINERS:-1}"

mkdir -p "$RUN_DIR"

echo "========== AssertFlip SWT-Bench Verified 全量运行 =========="
echo "数据集: $DATASET"
echo "运行目录: $RUN_DIR"
echo "结果目录: $RESULTS_DIR"
echo "run_tag: $RUN_TAG"
echo "limit: $LIMIT"
echo "AssertFlip workers: $WORKERS"
echo "运行 SWT-Bench 评测: $RUN_EVAL"
echo "SWT-Bench workers: $EVAL_WORKERS"
echo "SWT-Bench run_id: $EVAL_RUN_ID"
echo "SWT-Bench cache_level: $EVAL_CACHE_LEVEL"
echo "SWT-Bench reuse containers: $SWT_REUSE_CONTAINERS"
echo "SWT-Bench keep containers: $SWT_KEEP_CONTAINERS"
echo "GitHub proxy: $GITHUB_PROXY"
echo "=========================================================="

"$ROOT_DIR/scripts/run_assertflip_full.sh"

PREDS_FILE="${PREDS_FILE:-$RESULTS_DIR/preds_${RUN_TAG}.jsonl}"
MODEL_NAME_FOR_EVAL="${MODEL_NAME_FOR_EVAL:-AssertFlipLocal_${RUN_TAG}}"
SWT_BENCH_DIR="${SWT_BENCH_DIR:-/root/Baxxhy/BugReproduce/swt-bench}"
LOCAL_REPORT_JSON="$RUN_DIR/swtbench_eval_${EVAL_RUN_ID}.json"
SWT_REPORT_JSON="$SWT_BENCH_DIR/evaluation_results/${MODEL_NAME_FOR_EVAL}.${EVAL_RUN_ID}.json"

REPORT_FOR_VIS=""
if [[ -f "$LOCAL_REPORT_JSON" ]]; then
  REPORT_FOR_VIS="$LOCAL_REPORT_JSON"
elif [[ -f "$SWT_REPORT_JSON" ]]; then
  REPORT_FOR_VIS="$SWT_REPORT_JSON"
fi

VIS_PREFIX="$RUN_DIR/final_visual_summary_${RUN_TAG}"

VIS_ARGS=(
  --run-tag "$RUN_TAG"
  --dataset "$DATASET"
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

echo "========== 输出文件 =========="
echo "AssertFlip 文本汇总: $OUT_TXT"
echo "Predictions JSONL: $PREDS_FILE"
echo "可视化 HTML: ${VIS_PREFIX}.html"
echo "汇总 JSON: ${VIS_PREFIX}.json"
echo "汇总 CSV: ${VIS_PREFIX}.csv"
if [[ -n "$REPORT_FOR_VIS" ]]; then
  echo "SWT-Bench 评测 JSON: $REPORT_FOR_VIS"
fi
