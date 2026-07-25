#!/usr/bin/env bash
set -euo pipefail
: "${SALAD_API_KEY:?Set SALAD_API_KEY}"
: "${SALAD_ORGANIZATION:?Set SALAD_ORGANIZATION}"
: "${SALAD_PROJECT:?Set SALAD_PROJECT}"
BASE="https://api.salad.com/api/public/organizations/${SALAD_ORGANIZATION}/projects/${SALAD_PROJECT}"

create_queue() {
  local name="$1" display="$2"
  curl --fail-with-body -X POST "${BASE}/queues" \
    -H "Salad-Api-Key: ${SALAD_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"${name}\",\"display_name\":\"${display}\",\"description\":\"Created by WanGP + VoxCPM2 starter\"}"
}

create_queue "${SALAD_VOX_QUEUE:-voxcpm2-jobs}" "VoxCPM2 Jobs"
create_queue "${SALAD_WAN_QUEUE:-wangp-jobs}" "WanGP Jobs"
