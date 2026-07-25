#!/usr/bin/env bash
set -euo pipefail
: "${SALAD_API_KEY:?Set SALAD_API_KEY}"
: "${SALAD_ORGANIZATION:?Set SALAD_ORGANIZATION}"
: "${SALAD_PROJECT:?Set SALAD_PROJECT}"
FILE="${1:?Usage: deploy-container.sh <container-json>}"
curl --fail-with-body -X POST \
  "https://api.salad.com/api/public/organizations/${SALAD_ORGANIZATION}/projects/${SALAD_PROJECT}/containers" \
  -H "Salad-Api-Key: ${SALAD_API_KEY}" \
  -H "Content-Type: application/json" \
  --data-binary "@${FILE}"
