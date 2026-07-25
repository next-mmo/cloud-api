#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env VAST_API_KEY

RESPONSE_FILE="$(mktemp)"
trap 'rm -f "${RESPONSE_FILE}"' EXIT

curl --fail-with-body -sS \
  "${VAST_API_ROOT}/instances/" \
  -H "Authorization: Bearer ${VAST_API_KEY}" \
  -H "Accept: application/json" > "${RESPONSE_FILE}"

python3 -m json.tool "${RESPONSE_FILE}"
