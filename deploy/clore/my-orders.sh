#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env CLORE_API_KEY

RESPONSE_FILE="$(mktemp)"
trap 'rm -f "${RESPONSE_FILE}"' EXIT

curl --fail-with-body -sS \
  "${CLORE_API_ROOT}/my_orders${1:+?return_completed=true}" \
  -H "auth: ${CLORE_API_KEY}" \
  -H "Accept: application/json" > "${RESPONSE_FILE}"

clore_check_code "${RESPONSE_FILE}"
python3 -m json.tool "${RESPONSE_FILE}"
