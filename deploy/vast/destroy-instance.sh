#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env VAST_API_KEY

INSTANCE_ID="${1:-${VAST_INSTANCE_ID:-}}"
if [[ -z "${INSTANCE_ID}" ]]; then
  echo "Set VAST_INSTANCE_ID in .env, or pass: destroy-instance.sh <instance-id>" >&2
  exit 1
fi

RESPONSE_FILE="$(mktemp)"
trap 'rm -f "${RESPONSE_FILE}"' EXIT

curl --fail-with-body -sS -X DELETE \
  "${VAST_API_ROOT}/instances/${INSTANCE_ID}/" \
  -H "Authorization: Bearer ${VAST_API_KEY}" \
  -H "Accept: application/json" > "${RESPONSE_FILE}"

python3 -m json.tool "${RESPONSE_FILE}"
echo "Destroyed instance ${INSTANCE_ID}"
