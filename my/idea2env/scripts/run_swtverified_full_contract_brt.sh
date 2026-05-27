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

export RUN_TAG="${RUN_TAG:-swt_verified_contract_brt_full}"
export DATASET="${DATASET:-$ROOT_DIR/datasets/SWT_Verified_Agentless_Test_Source_Skeleton.json}"
export RUN_DIR="${RUN_DIR:-$ROOT_DIR/results/assertflip_${RUN_TAG}_run}"
export RESULTS_DIR="${RESULTS_DIR:-$RUN_DIR/results}"
export OUT_TXT="${OUT_TXT:-$RUN_DIR/assertflip_${RUN_TAG}_summary.txt}"
export EVAL_JSON="${EVAL_JSON:-$ROOT_DIR/results/evaluation_results_on_SWT_Bench/assertFlip_default_run.json}"
export LIMIT="${LIMIT:-1000000000}"
export WORKERS="${WORKERS:-1}"
export RUN_EVAL="${RUN_EVAL:-1}"

export EVAL_WORKERS="${EVAL_WORKERS:-1}"
export EVAL_TIMEOUT="${EVAL_TIMEOUT:-1800}"
export EVAL_RUN_ID="${EVAL_RUN_ID:-$RUN_TAG}"
export EVAL_CACHE_LEVEL="${EVAL_CACHE_LEVEL:-instance}"
export EVAL_BUILD_MODE="${EVAL_BUILD_MODE:-api}"
export EVAL_FILTER_SWT="${EVAL_FILTER_SWT:-1}"
export GITHUB_PROXY="${GITHUB_PROXY:-https://ghfast.top/}"
export GITHUB_MIRROR="${GITHUB_MIRROR:-$GITHUB_PROXY}"
export CONTRACT_BRT_CONSERVATIVE_MERGE="${CONTRACT_BRT_CONSERVATIVE_MERGE:-0}"
export CONTRACT_BRT_BASE_PREDS_FILE="${CONTRACT_BRT_BASE_PREDS_FILE:-}"
export CONTRACT_BRT_CONTRACT_PREDS_FILE="${CONTRACT_BRT_CONTRACT_PREDS_FILE:-}"
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

LOG_DIR="$ROOT_DIR/logs"
RUN_STARTED_AT="$(date '+%Y%m%d_%H%M%S')"
LOG_FILE="${LOG_FILE:-$LOG_DIR/run_${RUN_TAG}_${RUN_STARTED_AT}.log}"
mkdir -p "$LOG_DIR" "$RUN_DIR" "$RESULTS_DIR" "$CONTRACT_BRT_CONTRACT_DIR" "$CONTRACT_BRT_GENERATED_TEST_DIR"

if [[ "${CONTRACT_BRT_LOG_ACTIVE:-0}" != "1" ]]; then
  export CONTRACT_BRT_LOG_ACTIVE=1
  exec > >(tee -a "$LOG_FILE") 2>&1
fi

bash "$ROOT_DIR/scripts/prepare_contract_workspace.sh"

echo "========== Contract-BRT SWT-Bench Verified 全量运行 =========="
echo "Contract-BRT enabled"
echo "CONTRACT_BRT_ROOT=$CONTRACT_BRT_ROOT"
echo "result dir=$RUN_DIR"
echo "log file=$LOG_FILE"
echo "container reuse: disabled"
echo "container preservation: disabled"
echo "数据集: $DATASET"
echo "结果目录: $RESULTS_DIR"
echo "contracts: $CONTRACT_BRT_CONTRACT_DIR"
echo "generated tests: $CONTRACT_BRT_GENERATED_TEST_DIR"
echo "scaffold mode: $CONTRACT_BRT_SCAFFOLD_MODE"
echo "prompt mode: $CONTRACT_BRT_PROMPT_MODE"
echo "include scaffold in prompt: $CONTRACT_BRT_INCLUDE_SCAFFOLD_IN_PROMPT"
echo "preflight strictness: $CONTRACT_BRT_STRICTNESS"
echo "preflight mode: $CONTRACT_BRT_PREFLIGHT_MODE"
echo "conservative ECG merge: $CONTRACT_BRT_CONSERVATIVE_MERGE"
if [[ "$CONTRACT_BRT_CONSERVATIVE_MERGE" == "1" ]]; then
  echo "base preds file: $CONTRACT_BRT_BASE_PREDS_FILE"
fi
echo "模型: $MODEL"
echo "流程: $PHASE"
echo "Python runner: $PYTHON_BIN"
echo "limit: $LIMIT"
echo "workers: $WORKERS"
echo "运行 SWT-Bench 评测: $RUN_EVAL"
echo "SWT-Bench eval workers: $EVAL_WORKERS"
echo "GitHub mirror: $GITHUB_MIRROR"
echo "============================================================="

cd "$ROOT_DIR/scripts"
"$PYTHON_BIN" run_taxonomy_sample_20.py \
  --limit "$LIMIT" \
  --dataset "$DATASET" \
  --results-dir "$RESULTS_DIR" \
  --model "$MODEL" \
  --phase "$PHASE" \
  --workers "$WORKERS" \
  --max-generation-retries "$MAX_GENERATION_RETRIES" \
  --max-attempts "$MAX_ATTEMPTS"

cd "$ROOT_DIR"
echo "开始生成 Contract-BRT 本地汇总报告: $OUT_TXT"
"$PYTHON_BIN" scripts/summarize_assertflip_full.py \
  --dataset "$DATASET" \
  --results-dir "$RESULTS_DIR" \
  --eval-json "$EVAL_JSON" \
  --out-txt "$OUT_TXT" \
  --limit "$LIMIT"

PREDS_FILE="${PREDS_FILE:-$RESULTS_DIR/preds_${RUN_TAG}.jsonl}"
MODEL_NAME_FOR_EVAL="${MODEL_NAME_FOR_EVAL:-ContractBRTLocal_${RUN_TAG}}"
SWT_BENCH_DIR="${SWT_BENCH_DIR:-$ROOT_DIR/upstream/swt-bench}"
LOCAL_REPORT_JSON="$RUN_DIR/swtbench_eval_${EVAL_RUN_ID}.json"
SWT_REPORT_JSON="$SWT_BENCH_DIR/evaluation_results/${MODEL_NAME_FOR_EVAL}.${EVAL_RUN_ID}.json"

if [[ "$RUN_EVAL" == "1" ]]; then
  echo "开始运行 SWT-Bench 最终验证"
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
  echo "RUN_EVAL=0，跳过 SWT-Bench 最终验证"
  "$PYTHON_BIN" "$ROOT_DIR/scripts/generate_preds_phases.py" \
    --results-dir "$RESULTS_DIR" \
    --out-file "$PREDS_FILE" \
    --model-name "$MODEL_NAME_FOR_EVAL"
fi

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
  echo "警告: 没找到 SWT-Bench 评测报告，将只生成 Contract-BRT accepted 视角可视化。"
fi

"$PYTHON_BIN" "$ROOT_DIR/scripts/visualize_swtbench_verified_results.py" "${VIS_ARGS[@]}"

echo "========== 输出文件 =========="
echo "Contract-BRT 文本汇总: $OUT_TXT"
echo "Predictions JSONL: $PREDS_FILE"
echo "可视化 HTML: ${VIS_PREFIX}.html"
echo "汇总 JSON: ${VIS_PREFIX}.json"
echo "汇总 CSV: ${VIS_PREFIX}.csv"
echo "contracts: $CONTRACT_BRT_CONTRACT_DIR"
echo "generated tests: $CONTRACT_BRT_GENERATED_TEST_DIR"
echo "日志文件: $LOG_FILE"
