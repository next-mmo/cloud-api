#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env CLORE_API_KEY

ORDER_ID="${1:?Usage: cancel-order.sh <order-id>}"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "${RESPONSE_FILE}"' EXIT

curl --fail-with-body -sS -X POST \
  "${CLORE_API_ROOT}/cancel_order" \
  -H "auth: ${CLORE_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"id\": ${ORDER_ID}}" > "${RESPONSE_FILE}"

clore_check_code "${RESPONSE_FILE}"
python3 -m json.tool "${RESPONSE_FILE}"
