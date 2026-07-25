#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env SALAD_API_KEY SALAD_ORGANIZATION

curl --fail-with-body -sS \
  "${SALAD_ORG_BASE}/gpu-classes" \
  -H "Salad-Api-Key: ${SALAD_API_KEY}" \
  -H "Accept: application/json"
