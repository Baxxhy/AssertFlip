#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

RESULTS_DIR="${RESULTS_DIR:?RESULTS_DIR is required}"
RUN_TAG="${RUN_TAG:-assertflip}"
MODEL_NAME_FOR_EVAL="${MODEL_NAME_FOR_EVAL:-AssertFlipLocal_${RUN_TAG}}"
PREDS_FILE="${PREDS_FILE:-$RESULTS_DIR/preds_${RUN_TAG}.jsonl}"
SWT_BENCH_DIR="${SWT_BENCH_DIR:-$ROOT_DIR/upstream/swt-bench}"
SWT_BENCH_REPO="${SWT_BENCH_REPO:-https://github.com/logic-star-ai/swt-bench.git}"
SWT_DATASET_NAME="${SWT_DATASET_NAME:-princeton-nlp/SWE-bench_Verified}"
SWT_SPLIT="${SWT_SPLIT:-test}"
EVAL_WORKERS="${EVAL_WORKERS:-1}"
EVAL_TIMEOUT="${EVAL_TIMEOUT:-1800}"
EVAL_RUN_ID="${EVAL_RUN_ID:-${RUN_TAG}_$(date '+%Y%m%d_%H%M%S')}"
EVAL_CACHE_LEVEL="${EVAL_CACHE_LEVEL:-env}"
EVAL_BUILD_MODE="${EVAL_BUILD_MODE:-api}"
EVAL_FILTER_SWT="${EVAL_FILTER_SWT:-1}"
INSTALL_SWT_BENCH="${INSTALL_SWT_BENCH:-1}"
GITHUB_PROXY="${GITHUB_PROXY:-https://ghfast.top/}"
GITHUB_MIRROR="${GITHUB_MIRROR:-$GITHUB_PROXY}"
DATASET="${DATASET:-}"
CONTRACT_BRT_CONSERVATIVE_MERGE="${CONTRACT_BRT_CONSERVATIVE_MERGE:-0}"
CONTRACT_BRT_BASE_PREDS_FILE="${CONTRACT_BRT_BASE_PREDS_FILE:-}"
CONTRACT_BRT_CONTRACT_PREDS_FILE="${CONTRACT_BRT_CONTRACT_PREDS_FILE:-$RESULTS_DIR/preds_${RUN_TAG}_contract_only.jsonl}"

mkdir -p "$RESULTS_DIR"

echo "========== SWT-Bench 验证开始 =========="
echo "结果目录: $RESULTS_DIR"
echo "预测文件: $PREDS_FILE"
echo "SWT-Bench 目录: $SWT_BENCH_DIR"
echo "评测数据集: $SWT_DATASET_NAME"
echo "评测 workers: $EVAL_WORKERS"
echo "评测 run_id: $EVAL_RUN_ID"
echo "评测 build mode: $EVAL_BUILD_MODE"
echo "GitHub 代理: $GITHUB_PROXY"
echo "GitHub 镜像: $GITHUB_MIRROR"
echo "保守合并 ECG rescue: $CONTRACT_BRT_CONSERVATIVE_MERGE"
if [[ "$CONTRACT_BRT_CONSERVATIVE_MERGE" == "1" ]]; then
  echo "裸 AssertFlip base preds: $CONTRACT_BRT_BASE_PREDS_FILE"
  echo "Contract-BRT only preds: $CONTRACT_BRT_CONTRACT_PREDS_FILE"
fi
echo "========================================"

if [[ "$CONTRACT_BRT_CONSERVATIVE_MERGE" == "1" ]]; then
  if [[ -z "$CONTRACT_BRT_BASE_PREDS_FILE" || ! -f "$CONTRACT_BRT_BASE_PREDS_FILE" ]]; then
    echo "CONTRACT_BRT_CONSERVATIVE_MERGE=1 需要有效的 CONTRACT_BRT_BASE_PREDS_FILE"
    exit 4
  fi
  rm -f "$CONTRACT_BRT_CONTRACT_PREDS_FILE" "$PREDS_FILE"
  "$PYTHON_BIN" "$ROOT_DIR/scripts/generate_preds_phases.py" \
    --results-dir "$RESULTS_DIR" \
    --out-file "$CONTRACT_BRT_CONTRACT_PREDS_FILE" \
    --model-name "$MODEL_NAME_FOR_EVAL"
  "$PYTHON_BIN" "$ROOT_DIR/scripts/merge_conservative_preds.py" \
    --base-preds "$CONTRACT_BRT_BASE_PREDS_FILE" \
    --contract-preds "$CONTRACT_BRT_CONTRACT_PREDS_FILE" \
    --out-file "$PREDS_FILE" \
    --model-name "$MODEL_NAME_FOR_EVAL"
else
  rm -f "$PREDS_FILE"
  "$PYTHON_BIN" "$ROOT_DIR/scripts/generate_preds_phases.py" \
    --results-dir "$RESULTS_DIR" \
    --out-file "$PREDS_FILE" \
    --model-name "$MODEL_NAME_FOR_EVAL"
fi

PRED_COUNT="$(grep -cve '^[[:space:]]*$' "$PREDS_FILE" || true)"
echo "生成可评测 predictions 条数: $PRED_COUNT"
if [[ "$PRED_COUNT" == "0" ]]; then
  echo "没有 AssertFlip 接受的测试，跳过 SWT-Bench 验证。"
  exit 0
fi

if [[ ! -d "$SWT_BENCH_DIR/.git" ]]; then
  if [[ "$INSTALL_SWT_BENCH" != "1" ]]; then
    echo "找不到 SWT-Bench 目录，且 INSTALL_SWT_BENCH=0：$SWT_BENCH_DIR"
    exit 2
  fi
  echo "本地没有 SWT-Bench harness，开始 clone: $SWT_BENCH_REPO"
  if [[ -n "$GITHUB_MIRROR" ]]; then
    git config --global "url.${GITHUB_MIRROR%/}/https://github.com/.insteadOf" "https://github.com/" || true
    echo "已设置 git clone 镜像重写: https://github.com/ -> ${GITHUB_MIRROR%/}/https://github.com/"
  fi
  git clone "$SWT_BENCH_REPO" "$SWT_BENCH_DIR"
fi

if [[ "$INSTALL_SWT_BENCH" == "1" ]]; then
  echo "安装/更新 SWT-Bench Python 依赖: pip install -e $SWT_BENCH_DIR"
  "$PYTHON_BIN" -m pip install -e "$SWT_BENCH_DIR"
fi

cd "$SWT_BENCH_DIR"

export GITHUB_PROXY
export GITHUB_MIRROR

FILTER_FLAG=()
if [[ "$EVAL_FILTER_SWT" == "1" ]]; then
  FILTER_FLAG=(--filter_swt)
fi

"$PYTHON_BIN" -m src.main \
  --dataset_name "$SWT_DATASET_NAME" \
  --split "$SWT_SPLIT" \
  --predictions_path "$PREDS_FILE" \
  "${FILTER_FLAG[@]}" \
  --max_workers "$EVAL_WORKERS" \
  --run_id "$EVAL_RUN_ID" \
  --timeout "$EVAL_TIMEOUT" \
  --cache_level "$EVAL_CACHE_LEVEL" \
  --build_mode "$EVAL_BUILD_MODE"

REPORT_JSON="$SWT_BENCH_DIR/evaluation_results/${MODEL_NAME_FOR_EVAL}.${EVAL_RUN_ID}.json"
LOCAL_REPORT_JSON="$(dirname "$RESULTS_DIR")/swtbench_eval_${EVAL_RUN_ID}.json"
LOCAL_REPORT_TXT="$(dirname "$RESULTS_DIR")/swtbench_eval_${EVAL_RUN_ID}_summary.txt"

if [[ ! -f "$REPORT_JSON" ]]; then
  echo "没有找到 SWT-Bench 评测 JSON: $REPORT_JSON"
  exit 3
fi

cp "$REPORT_JSON" "$LOCAL_REPORT_JSON"

"$PYTHON_BIN" - "$REPORT_JSON" "$LOCAL_REPORT_TXT" "$DATASET" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
dataset_path = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else None
data = json.loads(report_path.read_text())

accepted_total = int(data.get("total_instances", 0) or 0)
resolved = int(data.get("resolved_instances", 0) or 0)
unresolved = int(data.get("unresolved_instances", 0) or 0)
errors = int(data.get("error_instances", 0) or 0)
coverage = data.get("Mean coverage", 0) or 0
coverage_delta = data.get("Mean coverage delta", 0) or 0
full_total = accepted_total
if dataset_path and dataset_path.exists():
    try:
        full_total = len(json.loads(dataset_path.read_text()))
    except Exception:
        full_total = accepted_total

accepted_rate = (accepted_total / full_total * 100) if full_total else 0.0
f2p_rate_among_accepted = (resolved / accepted_total * 100) if accepted_total else 0.0
f2p_rate_among_full = (resolved / full_total * 100) if full_total else 0.0

lines = [
    "SWT-Bench 最终验证汇总",
    f"评测 JSON: {report_path}",
    f"原始数据集条数: {full_total}",
    f"进入 SWT-Bench 评测条数 / AssertFlip accepted: {accepted_total}",
    f"F2P 成功条数: {resolved}",
    f"F2P 失败条数: {unresolved}",
    f"评测错误条数: {errors}",
    f"AssertFlip accepted 率: {accepted_rate:.2f}%",
    f"F2P 成功率（全量分母）: {f2p_rate_among_full:.2f}%",
    f"F2P 成功率（accepted 分母）: {f2p_rate_among_accepted:.2f}%",
    f"平均覆盖率 Mean coverage: {coverage * 100:.2f}%",
    f"平均覆盖率增量 Mean coverage delta: {coverage_delta * 100:.2f}%",
    "",
    "说明:",
    "- 这里的 F2P 是 SWT-Bench harness 验证后的结果。",
    "- 全量分母用于报告整体方法效果；accepted 分母用于诊断通过 AssertFlip 生成筛选后的验证质量。",
]
out_path.write_text("\n".join(lines) + "\n")
print("\n".join(lines))
PY

echo "SWT-Bench 评测 JSON 已复制到: $LOCAL_REPORT_JSON"
echo "SWT-Bench 中文汇总已写入: $LOCAL_REPORT_TXT"
