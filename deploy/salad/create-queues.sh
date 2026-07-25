#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env SALAD_API_KEY SALAD_ORGANIZATION SALAD_PROJECT

create_queue() {
  local name="$1" display="$2"
  local response_file status
  response_file="$(mktemp)"
  status="$(curl -sS -o "${response_file}" -w '%{http_code}' \
    -X POST "${SALAD_BASE}/queues" \
    -H "Salad-Api-Key: ${SALAD_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"${name}\",\"display_name\":\"${display}\",\"description\":\"Created by WanGP + VoxCPM2 starter\"}")"

  if [[ "${status}" == "200" || "${status}" == "201" ]]; then
    cat "${response_file}"
    echo
  elif [[ "${status}" == "400" || "${status}" == "409" ]]; then
    echo "Queue may already exist: ${name}"
  else
    cat "${response_file}" >&2
    rm -f "${response_file}"
    return 1
  fi
  rm -f "${response_file}"
}

create_queue "${SALAD_VOX_QUEUE:-voxcpm2-jobs}" "VoxCPM2 Jobs"

if [[ "${CREATE_WAN_QUEUE:-false}" == "true" ]]; then
  create_queue "${SALAD_WAN_QUEUE:-wangp-jobs}" "WanGP Jobs"
fi
