#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
if [[ -f "$ROOT_DIR/scripts/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/scripts/.env"
  set +a
fi

DATASET="${DATASET:-datasets/SWT_Lite_Agentless_Test_Source_Skeleton.json}"
RELATED_TESTS="${RELATED_TESTS:-datasets/related_tests.json}"
BTCR_OUTPUT_DIR="${BTCR_OUTPUT_DIR:-btcr_results}"
MODEL="${MODEL:-gpt-4o-mini}"
DATASET_INDEX="${DATASET_INDEX:-0}"
MAX_GENERATION_RETRIES="${MAX_GENERATION_RETRIES:-1}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
PHASE="${PHASE:-pass_then_invert}"
TEST_CMD="${TEST_CMD:-pytest}"
PYTEST_ARGS="${PYTEST_ARGS:-}"

if [[ -z "${TESTS_DIR:-}" ]]; then
  if [[ -d /testbed/tests ]]; then
    TESTS_DIR="/testbed/tests"
  else
    TESTS_DIR="$ROOT_DIR/btcr_generated_tests"
    mkdir -p "$TESTS_DIR"
  fi
fi

if [[ -z "${SOURCE_DIR:-}" ]]; then
  if [[ -d /testbed ]]; then
    SOURCE_DIR="/testbed"
  else
    SOURCE_DIR="$ROOT_DIR"
  fi
fi

cmd=(
  python -m assertFlip
  --dataset "$DATASET"
  --dataset-index "$DATASET_INDEX"
  --source-dir "$SOURCE_DIR"
  --tests-dir "$TESTS_DIR"
  --related-tests "$RELATED_TESTS"
  --btcr-output-dir "$BTCR_OUTPUT_DIR"
  --model "$MODEL"
  --phase "$PHASE"
  --max-generation-retries "$MAX_GENERATION_RETRIES"
  --max-attempts "$MAX_ATTEMPTS"
  --test-cmd "$TEST_CMD"
)

if [[ -n "${INSTANCE_ID:-}" ]]; then
  cmd+=(--instance-id "$INSTANCE_ID")
fi

if [[ -n "$PYTEST_ARGS" ]]; then
  cmd+=(--pytest-args "$PYTEST_ARGS")
fi

PYTHONPATH="$ROOT_DIR/assertflip/src${PYTHONPATH:+:$PYTHONPATH}" "${cmd[@]}"
