#!/usr/bin/env bash
set -euo pipefail
: "${SALAD_API_KEY:?Set SALAD_API_KEY}"
: "${SALAD_ORGANIZATION:?Set SALAD_ORGANIZATION}"
curl --fail-with-body \
  "https://api.salad.com/api/public/organizations/${SALAD_ORGANIZATION}/gpu-classes" \
  -H "Salad-Api-Key: ${SALAD_API_KEY}" \
  -H "accept: application/json"
