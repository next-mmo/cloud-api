#!/usr/bin/env bash

# Shared local environment loader for Salad deployment scripts.
# By default it reads <repo-root>/.env. Override with ENV_FILE=/path/to/file.

SALAD_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SALAD_REPO_ROOT="$(cd "${SALAD_SCRIPT_DIR}/../.." && pwd)"
SALAD_ENV_FILE="${ENV_FILE:-${SALAD_REPO_ROOT}/.env}"

if [[ ! -f "${SALAD_ENV_FILE}" ]]; then
  echo "Missing ${SALAD_ENV_FILE}" >&2
  echo "Create it with: cp .env.example .env" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${SALAD_ENV_FILE}"
set +a

require_env() {
  local name
  for name in "$@"; do
    if [[ -z "${!name:-}" ]]; then
      echo "Missing ${name} in ${SALAD_ENV_FILE}" >&2
      exit 1
    fi
  done
}

SALAD_API_ROOT="${SALAD_API_ROOT:-https://api.salad.com/api/public}"

if [[ -n "${SALAD_ORGANIZATION:-}" ]]; then
  SALAD_ORG_BASE="${SALAD_API_ROOT}/organizations/${SALAD_ORGANIZATION}"
fi

if [[ -n "${SALAD_ORGANIZATION:-}" && -n "${SALAD_PROJECT:-}" ]]; then
  SALAD_BASE="${SALAD_ORG_BASE}/projects/${SALAD_PROJECT}"
fi

salad_headers() {
  printf '%s\n' \
    "Salad-Api-Key: ${SALAD_API_KEY}" \
    "Content-Type: application/json" \
    "Accept: application/json"
}
