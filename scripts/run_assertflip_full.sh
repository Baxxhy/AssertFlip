#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RUN_TAG="${RUN_TAG:-swt_lite_unique}"
DATASET="${DATASET:-$ROOT_DIR/datasets/SWT_Lite_Agentless_Unique_Only.json}"
RESULTS_DIR="${RESULTS_DIR:-$ROOT_DIR/assertflip_${RUN_TAG}_run/results}"
OUT_TXT="${OUT_TXT:-$ROOT_DIR/assertflip_${RUN_TAG}_run/assertflip_${RUN_TAG}_summary.txt}"
EVAL_JSON="${EVAL_JSON:-$ROOT_DIR/evaluation_results_on_SWT_Bench/assertFlip_Lite_unique_188_instances.json}"
MODEL="${MODEL:-openai/gpt-4o-mini}"
PHASE="${PHASE:-pass_then_invert}"
LIMIT="${LIMIT:-1000000000}"
WORKERS="${WORKERS:-1}"
MAX_GENERATION_RETRIES="${MAX_GENERATION_RETRIES:-3}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
DOCKER_CLIENT_TIMEOUT="${DOCKER_CLIENT_TIMEOUT:-600}"
DOCKER_IMAGE_REGISTRY="${DOCKER_IMAGE_REGISTRY:-docker.1ms.run}"
DOCKER_IMAGE_REGISTRIES="${DOCKER_IMAGE_REGISTRIES:-$DOCKER_IMAGE_REGISTRY}"
DOCKER_PULL_QUIET_TIMEOUT="${DOCKER_PULL_QUIET_TIMEOUT:-300}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
APT_MIRROR="${APT_MIRROR:-https://mirrors.tuna.tsinghua.edu.cn}"
REMOVE_IMAGE_AFTER_RUN="${REMOVE_IMAGE_AFTER_RUN:-0}"
RUN_EVAL="${RUN_EVAL:-0}"
export DOCKER_CLIENT_TIMEOUT
export DOCKER_IMAGE_REGISTRY
export DOCKER_IMAGE_REGISTRIES
export DOCKER_PULL_QUIET_TIMEOUT
export PIP_INDEX_URL
export APT_MIRROR
export REMOVE_IMAGE_AFTER_RUN

LOG_DIR="${LOG_DIR:-$ROOT_DIR/logs}"
RUN_STARTED_AT="$(date '+%Y%m%d_%H%M%S')"
LOG_FILE="${LOG_FILE:-$LOG_DIR/run_${RUN_TAG}_${RUN_STARTED_AT}.log}"
mkdir -p "$LOG_DIR"

if [[ "${ASSERTFLIP_LOG_ACTIVE:-0}" != "1" ]]; then
  export ASSERTFLIP_LOG_ACTIVE=1
  exec > >(tee -a "$LOG_FILE") 2>&1
fi

# Set RUN_GENERATION=0 to only regenerate the txt report from existing results/evaluation JSON.
RUN_GENERATION="${RUN_GENERATION:-1}"

mkdir -p "$RESULTS_DIR"

echo "========== AssertFlip 运行开始 =========="
echo "开始时间: $(date '+%F %T %Z')"
echo "日志文件: $LOG_FILE"
echo "数据集: $DATASET"
echo "结果目录: $RESULTS_DIR"
echo "汇总报告: $OUT_TXT"
echo "评测 JSON: $EVAL_JSON"
echo "模型: $MODEL"
echo "流程: $PHASE"
echo "并行 workers: $WORKERS"
echo "单阶段生成重试 max_generation_retries: $MAX_GENERATION_RETRIES"
echo "整体尝试轮数 max_attempts: $MAX_ATTEMPTS"
echo "Docker 镜像候选源: $DOCKER_IMAGE_REGISTRIES, 官方 Docker Hub"
echo "Docker 拉取无输出超时秒数: $DOCKER_PULL_QUIET_TIMEOUT"
echo "PyPI 镜像: $PIP_INDEX_URL"
echo "apt 镜像: $APT_MIRROR"
echo "每条结束后删除镜像: $REMOVE_IMAGE_AFTER_RUN"
echo "生成结束后运行 SWT-Bench 验证: $RUN_EVAL"
echo "========================================"

if [[ "$RUN_GENERATION" != "0" ]]; then
  cd "$ROOT_DIR/scripts"
  python run_taxonomy_sample_20.py \
    --limit "$LIMIT" \
    --dataset "$DATASET" \
    --results-dir "$RESULTS_DIR" \
    --model "$MODEL" \
    --phase "$PHASE" \
    --workers "$WORKERS" \
    --max-generation-retries "$MAX_GENERATION_RETRIES" \
    --max-attempts "$MAX_ATTEMPTS"
fi

cd "$ROOT_DIR"
echo "开始生成最终汇总报告: $OUT_TXT"
python scripts/summarize_assertflip_full.py \
  --dataset "$DATASET" \
  --results-dir "$RESULTS_DIR" \
  --eval-json "$EVAL_JSON" \
  --out-txt "$OUT_TXT" \
  --limit "$LIMIT"

echo "汇总报告已写入: $OUT_TXT"

if [[ "$RUN_EVAL" == "1" ]]; then
  echo "开始运行 SWT-Bench 最终验证"
  "$ROOT_DIR/scripts/run_swtbench_eval_for_results.sh"
fi

echo "日志文件: $LOG_FILE"
echo "结束时间: $(date '+%F %T %Z')"
