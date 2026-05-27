#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export RUN_TAG="${RUN_TAG:-swt_verified_author326_first100}"
export DATASET="${DATASET:-$ROOT_DIR/datasets/SWT_Verified_Agentless_Author_Default_326.json}"
export RESULTS_DIR="${RESULTS_DIR:-$ROOT_DIR/assertflip_swt_verified_author326_first100_run/results}"
export OUT_TXT="${OUT_TXT:-$ROOT_DIR/assertflip_swt_verified_author326_first100_run/assertflip_swt_verified_author326_first100_summary.txt}"
export EVAL_JSON="${EVAL_JSON:-$ROOT_DIR/evaluation_results_on_SWT_Bench/assertFlip_default_run.json}"
export LIMIT="${LIMIT:-100}"
export WORKERS="${WORKERS:-1}"
export RUN_EVAL="${RUN_EVAL:-1}"
export EVAL_WORKERS="${EVAL_WORKERS:-1}"
export DOCKER_PULL_QUIET_TIMEOUT="${DOCKER_PULL_QUIET_TIMEOUT:-600}"

exec "$ROOT_DIR/scripts/run_assertflip_full.sh"
