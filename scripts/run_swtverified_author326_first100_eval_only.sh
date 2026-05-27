#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export RUN_TAG="${RUN_TAG:-swt_verified_author326_first100}"
export RESULTS_DIR="${RESULTS_DIR:-$ROOT_DIR/assertflip_swt_verified_author326_first100_run/results}"
export EVAL_WORKERS="${EVAL_WORKERS:-1}"
export EVAL_BUILD_MODE="${EVAL_BUILD_MODE:-api}"
export GITHUB_PROXY="${GITHUB_PROXY:-https://ghfast.top/}"
export INSTALL_SWT_BENCH="${INSTALL_SWT_BENCH:-1}"

exec "$ROOT_DIR/scripts/run_swtbench_eval_for_results.sh"
