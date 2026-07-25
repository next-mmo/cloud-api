#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env CLORE_API_KEY

ORDER_SRC="${1:-${SCRIPT_DIR}/order-voxcpm2.json}"
if [[ ! -f "${ORDER_SRC}" ]]; then
  echo "Missing ${ORDER_SRC}" >&2
  echo "Copy and edit the order template first:" >&2
  echo "  cp deploy/clore/order-voxcpm2.json.template deploy/clore/order-voxcpm2.json" >&2
  exit 1
fi

if [[ -z "${CLORE_SERVER_ID:-}" ]]; then
  echo "CLORE_SERVER_ID is not set." >&2
  echo "Find a server first, for example:" >&2
  echo "  ./deploy/clore/list-marketplace.sh 'RTX 4090'" >&2
  exit 1
fi

echo "Creating Clore order for server ${CLORE_SERVER_ID}..."
CREATE_OUT="$("${SCRIPT_DIR}/create-order.sh" "${ORDER_SRC}")"
echo "${CREATE_OUT}"
ORDER_ID="$(printf '%s\n' "${CREATE_OUT}" | awk '/^Order ID:/{print $3; exit}')"
if [[ -z "${ORDER_ID}" ]]; then
  echo "Could not parse order id from create-order output" >&2
  exit 1
fi

"${SCRIPT_DIR}/wait-order.sh" "${ORDER_ID}" 8011
