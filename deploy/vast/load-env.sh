#!/usr/bin/env bash

# Shared local environment loader for Vast.ai deployment scripts.
# By default it reads <repo-root>/.env. Override with ENV_FILE=/path/to/file.

VAST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAST_REPO_ROOT="$(cd "${VAST_SCRIPT_DIR}/../.." && pwd)"
VAST_ENV_FILE="${ENV_FILE:-${VAST_REPO_ROOT}/.env}"

if [[ ! -f "${VAST_ENV_FILE}" ]]; then
  echo "Missing ${VAST_ENV_FILE}" >&2
  echo "Create it with: cp .env.example .env" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${VAST_ENV_FILE}"
set +a

# Common aliases used by Vast CLI/SDK docs.
VAST_API_KEY="${VAST_API_KEY:-${VASTAI_API_KEY:-}}"

require_env() {
  local name
  for name in "$@"; do
    if [[ -z "${!name:-}" ]]; then
      echo "Missing ${name} in ${VAST_ENV_FILE}" >&2
      exit 1
    fi
  done
}

VAST_API_ROOT="${VAST_API_ROOT:-https://console.vast.ai/api/v0}"
