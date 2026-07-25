#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env VAST_API_KEY

INSTANCE_SRC="${1:-${SCRIPT_DIR}/instance-voxcpm2.json}"
if [[ ! -f "${INSTANCE_SRC}" ]]; then
  echo "Missing ${INSTANCE_SRC}" >&2
  echo "Copy and edit the instance template first:" >&2
  echo "  cp deploy/vast/instance-voxcpm2.json.template deploy/vast/instance-voxcpm2.json" >&2
  exit 1
fi

if [[ -z "${VAST_OFFER_ID:-}" ]]; then
  echo "VAST_OFFER_ID is not set in .env" >&2
  echo "Find an offer first, for example:" >&2
  echo "  ./deploy/vast/list-offers.sh 'RTX 4090'" >&2
  echo "Then add VAST_OFFER_ID=... to .env" >&2
  exit 1
fi

echo "Creating Vast instance from offer ${VAST_OFFER_ID}..."
CREATE_OUT="$("${SCRIPT_DIR}/create-instance.sh" "${INSTANCE_SRC}" "${VAST_OFFER_ID}")"
echo "${CREATE_OUT}"
INSTANCE_ID="$(printf '%s\n' "${CREATE_OUT}" | awk '/^Instance ID:/{print $3; exit}')"
if [[ -z "${INSTANCE_ID}" ]]; then
  echo "Could not parse instance id from create-instance output" >&2
  exit 1
fi

"${SCRIPT_DIR}/wait-instance.sh" "${INSTANCE_ID}" 8011
