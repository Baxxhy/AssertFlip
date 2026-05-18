#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export RUN_TAG="${RUN_TAG:-swt_lite_unique}"
export DATASET="${DATASET:-$ROOT_DIR/datasets/SWT_Lite_Agentless_Unique_Only.json}"
export RESULTS_DIR="${RESULTS_DIR:-$ROOT_DIR/assertflip_swt_lite_unique_run/results}"
export OUT_TXT="${OUT_TXT:-$ROOT_DIR/assertflip_swt_lite_unique_run/assertflip_swt_lite_unique_summary.txt}"
export EVAL_JSON="${EVAL_JSON:-$ROOT_DIR/evaluation_results_on_SWT_Bench/assertFlip_Lite_unique_188_instances.json}"

exec "$ROOT_DIR/scripts/run_assertflip_full.sh"
