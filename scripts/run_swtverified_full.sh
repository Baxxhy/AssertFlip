#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export RUN_TAG="${RUN_TAG:-swt_verified}"
export DATASET="${DATASET:-$ROOT_DIR/datasets/SWT_Verified_Agentless_Test_Source_Skeleton.json}"
export RESULTS_DIR="${RESULTS_DIR:-$ROOT_DIR/assertflip_swt_verified_run/results}"
export OUT_TXT="${OUT_TXT:-$ROOT_DIR/assertflip_swt_verified_run/assertflip_swt_verified_summary.txt}"
export EVAL_JSON="${EVAL_JSON:-$ROOT_DIR/evaluation_results_on_SWT_Bench/assertFlip_default_run.json}"

exec "$ROOT_DIR/scripts/run_assertflip_full.sh"
