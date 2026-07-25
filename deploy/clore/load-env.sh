#!/usr/bin/env bash

# Shared local environment loader for Clore.ai deployment scripts.
# By default it reads <repo-root>/.env. Override with ENV_FILE=/path/to/file.

CLORE_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLORE_REPO_ROOT="$(cd "${CLORE_SCRIPT_DIR}/../.." && pwd)"
CLORE_ENV_FILE="${ENV_FILE:-${CLORE_REPO_ROOT}/.env}"

if [[ ! -f "${CLORE_ENV_FILE}" ]]; then
  echo "Missing ${CLORE_ENV_FILE}" >&2
  echo "Create it with: cp .env.example .env" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${CLORE_ENV_FILE}"
set +a

require_env() {
  local name
  for name in "$@"; do
    if [[ -z "${!name:-}" ]]; then
      echo "Missing ${name} in ${CLORE_ENV_FILE}" >&2
      exit 1
    fi
  done
}

CLORE_API_ROOT="${CLORE_API_ROOT:-https://api.clore.ai/v1}"

clore_headers() {
  printf '%s\n' \
    "auth: ${CLORE_API_KEY}" \
    "Content-Type: application/json" \
    "Accept: application/json"
}

clore_check_code() {
  local file="$1"
  python3 - "$file" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    data = json.load(handle)
code = data.get("code")
if code != 0:
    err = data.get("error") or data
    raise SystemExit(f"Clore API error code={code}: {err}")
PY
}
