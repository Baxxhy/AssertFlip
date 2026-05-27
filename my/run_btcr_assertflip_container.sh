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
INSTANCE_ID="${INSTANCE_ID:-}"
DATASET_INDEX="${DATASET_INDEX:-0}"

if [[ -z "$INSTANCE_ID" ]]; then
  INSTANCE_ID="$(python - "$DATASET" "$DATASET_INDEX" <<'PY'
import json
import sys
path, index = sys.argv[1], int(sys.argv[2])
with open(path) as f:
    data = json.load(f)
if isinstance(data, list):
    print(data[index].get("instance_id", f"dataset_index_{index}"))
else:
    print(data.get("instance_id", "unknown_instance"))
PY
)"
fi

DEFAULT_CONTAINER="btcr_${INSTANCE_ID//[^A-Za-z0-9_.-]/_}"
CONTAINER="${CONTAINER:-$DEFAULT_CONTAINER}"
IMAGE="${IMAGE:-}"
AUTO_IMAGE="${AUTO_IMAGE:-1}"

container_exists() {
  docker inspect "$1" >/dev/null 2>&1
}

container_running() {
  [[ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null || true)" == "true" ]]
}

if container_exists "$CONTAINER"; then
  if ! container_running "$CONTAINER"; then
    docker start "$CONTAINER" >/dev/null
  fi
else
  if [[ -z "$IMAGE" && "$AUTO_IMAGE" == "1" ]]; then
    repo_part="${INSTANCE_ID%%__*}"
    issue_part="${INSTANCE_ID#*__}"
    image_pattern="${repo_part}_1776_${issue_part}"
    IMAGE="$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -F "$image_pattern" | head -n 1 || true)"
  fi
  if [[ -z "$IMAGE" ]]; then
    cat >&2 <<EOF
Container '$CONTAINER' does not exist, and IMAGE was not provided.

Use one of these forms:
  CONTAINER=<existing_container_name> ./run_btcr_assertflip_container.sh
  IMAGE=<swebench_eval_or_env_image> ./run_btcr_assertflip_container.sh
  AUTO_IMAGE=1 ./run_btcr_assertflip_container.sh

Existing containers:
EOF
    docker ps -a --format '  {{.Names}}  {{.Image}}  {{.Status}}' >&2
    exit 2
  fi
  docker run -d \
    --name "$CONTAINER" \
    -v "$ROOT_DIR:$ROOT_DIR" \
    -w "$ROOT_DIR" \
    "$IMAGE" \
    sleep infinity >/dev/null
fi

docker exec \
  -e INSTANCE_ID="$INSTANCE_ID" \
  "$CONTAINER" \
  bash -lc 'rm -f "/testbed/tests/test_assertflip_${INSTANCE_ID}.py" "/testbed/tests/disabled_test_assertflip_${INSTANCE_ID}.py" 2>/dev/null || true'

docker exec \
  -e DATASET="$DATASET" \
  -e RELATED_TESTS="${RELATED_TESTS:-datasets/related_tests.json}" \
  -e BTCR_OUTPUT_DIR="${BTCR_OUTPUT_DIR:-btcr_results}" \
  -e MODEL="${MODEL:-gpt-4o-mini}" \
  -e DATASET_INDEX="$DATASET_INDEX" \
  -e INSTANCE_ID="$INSTANCE_ID" \
  -e MAX_GENERATION_RETRIES="${MAX_GENERATION_RETRIES:-1}" \
  -e MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}" \
  -e PHASE="${PHASE:-pass_then_invert}" \
  -e TEST_CMD="${TEST_CMD:-pytest}" \
  -e PYTEST_ARGS="${PYTEST_ARGS:-}" \
  -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
  "$CONTAINER" \
  bash "$ROOT_DIR/run_btcr_assertflip.sh"

docker exec \
  -e INSTANCE_ID="$INSTANCE_ID" \
  "$CONTAINER" \
  bash -lc 'rm -f "/testbed/tests/test_assertflip_${INSTANCE_ID}.py" "/testbed/tests/disabled_test_assertflip_${INSTANCE_ID}.py" 2>/dev/null || true'
