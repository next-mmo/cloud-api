#!/usr/bin/env bash

# Shared local environment loader for RunPod deployment scripts.
# By default it reads <repo-root>/.env. Override with ENV_FILE=/path/to/file.

RUNPOD_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNPOD_REPO_ROOT="$(cd "${RUNPOD_SCRIPT_DIR}/../.." && pwd)"
RUNPOD_ENV_FILE="${ENV_FILE:-${RUNPOD_REPO_ROOT}/.env}"

if [[ ! -f "${RUNPOD_ENV_FILE}" ]]; then
  echo "Missing ${RUNPOD_ENV_FILE}" >&2
  echo "Create it with: cp .env.example .env" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${RUNPOD_ENV_FILE}"
set +a

require_env() {
  local name
  for name in "$@"; do
    if [[ -z "${!name:-}" ]]; then
      echo "Missing ${name} in ${RUNPOD_ENV_FILE}" >&2
      exit 1
    fi
  done
}

RUNPOD_REST_ROOT="${RUNPOD_REST_ROOT:-https://rest.runpod.io/v1}"
RUNPOD_JOB_ROOT="${RUNPOD_JOB_ROOT:-https://api.runpod.ai/v2}"

runpod_headers() {
  printf '%s\n' \
    "Authorization: Bearer ${RUNPOD_API_KEY}" \
    "Content-Type: application/json" \
    "Accept: application/json"
}
