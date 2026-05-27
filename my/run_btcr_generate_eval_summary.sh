#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$ROOT_DIR/scripts/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/scripts/.env"
  set +a
fi

export RUN_TAG="${RUN_TAG:-swt_verified_btcr_full}"
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
export SWT_REUSE_CONTAINERS="${SWT_REUSE_CONTAINERS:-1}"
export SWT_KEEP_CONTAINERS="${SWT_KEEP_CONTAINERS:-1}"

export DOCKER_CLIENT_TIMEOUT="${DOCKER_CLIENT_TIMEOUT:-600}"
export DOCKER_IMAGE_REGISTRY="${DOCKER_IMAGE_REGISTRY:-docker.1ms.run}"
export DOCKER_IMAGE_REGISTRIES="${DOCKER_IMAGE_REGISTRIES:-$DOCKER_IMAGE_REGISTRY}"
export DOCKER_PULL_QUIET_TIMEOUT="${DOCKER_PULL_QUIET_TIMEOUT:-300}"
export PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
export APT_MIRROR="${APT_MIRROR:-https://mirrors.tuna.tsinghua.edu.cn}"
export REMOVE_IMAGE_AFTER_RUN="${REMOVE_IMAGE_AFTER_RUN:-0}"

export MODEL="${MODEL:-openai/gpt-4o-mini}"
export PHASE="${PHASE:-pass_then_invert}"
export MAX_GENERATION_RETRIES="${MAX_GENERATION_RETRIES:-3}"
export MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
export INSTANCE_TIMEOUT="${INSTANCE_TIMEOUT:-3600}"
export RUN_GENERATION="${RUN_GENERATION:-1}"

LOG_DIR="${LOG_DIR:-$ROOT_DIR/logs}"
RUN_STARTED_AT="$(date '+%Y%m%d_%H%M%S')"
LOG_FILE="${LOG_FILE:-$LOG_DIR/run_${RUN_TAG}_${RUN_STARTED_AT}.log}"
mkdir -p "$LOG_DIR"

if [[ "${ASSERTFLIP_BTCR_LOG_ACTIVE:-0}" != "1" ]]; then
  export ASSERTFLIP_BTCR_LOG_ACTIVE=1
  exec > >(tee -a "$LOG_FILE") 2>&1
fi

mkdir -p "$RUN_DIR" "$RESULTS_DIR"

echo "========== AssertFlip+BTCR SWT-Bench Verified 全量运行 =========="
echo "开始时间: $(date '+%F %T %Z')"
echo "日志文件: $LOG_FILE"
echo "数据集: $DATASET"
echo "运行目录: $RUN_DIR"
echo "结果目录: $RESULTS_DIR"
echo "汇总报告: $OUT_TXT"
echo "评测 JSON: $EVAL_JSON"
echo "模型: $MODEL"
echo "流程: $PHASE"
echo "run_tag: $RUN_TAG"
echo "limit: $LIMIT"
echo "AssertFlip+BTCR workers: $WORKERS"
echo "单阶段生成重试 max_generation_retries: $MAX_GENERATION_RETRIES"
echo "整体尝试轮数 max_attempts: $MAX_ATTEMPTS"
echo "运行 SWT-Bench 评测: $RUN_EVAL"
echo "SWT-Bench workers: $EVAL_WORKERS"
echo "SWT-Bench run_id: $EVAL_RUN_ID"
echo "SWT-Bench cache_level: $EVAL_CACHE_LEVEL"
echo "SWT-Bench reuse containers: $SWT_REUSE_CONTAINERS"
echo "SWT-Bench keep containers: $SWT_KEEP_CONTAINERS"
echo "GitHub proxy: $GITHUB_PROXY"
echo "Docker 镜像候选源: $DOCKER_IMAGE_REGISTRIES, 官方 Docker Hub"
echo "Docker 拉取无输出超时秒数: $DOCKER_PULL_QUIET_TIMEOUT"
echo "PyPI 镜像: $PIP_INDEX_URL"
echo "apt 镜像: $APT_MIRROR"
echo "生成阶段容器策略: 同名复用，跑完保留，清理插入的 test_assertflip 文件"
echo "==============================================================="

if [[ "$RUN_GENERATION" != "0" ]]; then
  python "$ROOT_DIR/scripts/run_btcr_generation_full.py" \
    --dataset "$DATASET" \
    --results-dir "$RESULTS_DIR" \
    --root-dir "$ROOT_DIR" \
    --model "$MODEL" \
    --phase "$PHASE" \
    --limit "$LIMIT" \
    --workers "$WORKERS" \
    --max-generation-retries "$MAX_GENERATION_RETRIES" \
    --max-attempts "$MAX_ATTEMPTS" \
    --instance-timeout "$INSTANCE_TIMEOUT"
fi

cd "$ROOT_DIR"
echo "开始生成 AssertFlip+BTCR 本地汇总报告: $OUT_TXT"
python scripts/summarize_assertflip_full.py \
  --dataset "$DATASET" \
  --results-dir "$RESULTS_DIR" \
  --eval-json "$EVAL_JSON" \
  --out-txt "$OUT_TXT" \
  --limit "$LIMIT"

PREDS_FILE="${PREDS_FILE:-$RESULTS_DIR/preds_${RUN_TAG}.jsonl}"
MODEL_NAME_FOR_EVAL="${MODEL_NAME_FOR_EVAL:-AssertFlipBTCRLocal_${RUN_TAG}}"
SWT_BENCH_DIR="${SWT_BENCH_DIR:-/root/Baxxhy/BugReproduce/swt-bench}"
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
  DATASET="$DATASET" \
  bash "$ROOT_DIR/scripts/run_swtbench_eval_for_results.sh"
else
  echo "RUN_EVAL=0，跳过 SWT-Bench 最终验证"
  python "$ROOT_DIR/scripts/generate_preds_phases.py" \
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
  echo "警告: 没找到 SWT-Bench 评测报告，将只生成 AssertFlip+BTCR accepted 视角可视化。"
fi

python "$ROOT_DIR/scripts/visualize_swtbench_verified_results.py" "${VIS_ARGS[@]}"

echo "========== 输出文件 =========="
echo "AssertFlip+BTCR 文本汇总: $OUT_TXT"
echo "Predictions JSONL: $PREDS_FILE"
echo "可视化 HTML: ${VIS_PREFIX}.html"
echo "汇总 JSON: ${VIS_PREFIX}.json"
echo "汇总 CSV: ${VIS_PREFIX}.csv"
if [[ -n "$REPORT_FOR_VIS" ]]; then
  echo "SWT-Bench 评测 JSON: $REPORT_FOR_VIS"
fi
echo "日志文件: $LOG_FILE"
echo "结束时间: $(date '+%F %T %Z')"
