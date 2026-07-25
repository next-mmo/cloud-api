#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env RUNPOD_API_KEY

FILE="${1:?Usage: create-template.sh <template-json>}"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "${RESPONSE_FILE}"' EXIT

curl --fail-with-body -sS -X POST \
  "${RUNPOD_REST_ROOT}/templates" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  --data-binary "@${FILE}" > "${RESPONSE_FILE}"

python3 -m json.tool "${RESPONSE_FILE}"
TEMPLATE_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "${RESPONSE_FILE}")"
echo
echo "Template ID: ${TEMPLATE_ID}"
echo "Set this as templateId in your endpoint JSON, then run create-endpoint.sh."
