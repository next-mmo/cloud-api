#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env RUNPOD_API_KEY

TEMPLATE_SRC="${1:-${SCRIPT_DIR}/template-voxcpm2.json}"
ENDPOINT_SRC="${2:-${SCRIPT_DIR}/endpoint-voxcpm2.json}"

if [[ ! -f "${TEMPLATE_SRC}" ]]; then
  echo "Missing ${TEMPLATE_SRC}" >&2
  echo "Copy the template first:" >&2
  echo "  cp deploy/runpod/template-voxcpm2.json.template deploy/runpod/template-voxcpm2.json" >&2
  exit 1
fi
if [[ ! -f "${ENDPOINT_SRC}" ]]; then
  echo "Missing ${ENDPOINT_SRC}" >&2
  echo "Copy the endpoint template first:" >&2
  echo "  cp deploy/runpod/endpoint-voxcpm2.json.template deploy/runpod/endpoint-voxcpm2.json" >&2
  exit 1
fi

python3 - "${TEMPLATE_SRC}" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    payload = json.load(handle)
image = str(payload.get("imageName") or "")
if not image or "YOUR_REGISTRY" in image:
    raise SystemExit(f"Set a real imageName in {path} (got: {image!r})")
env = payload.get("env") or {}
if str(env.get("RUNPOD_HANDLER_ENABLED", "0")) != "1":
    raise SystemExit("template env.RUNPOD_HANDLER_ENABLED must be \"1\"")
if str(env.get("SALAD_QUEUE_WORKER_ENABLED", "1")) != "0":
    raise SystemExit("template env.SALAD_QUEUE_WORKER_ENABLED must be \"0\" for RunPod")
PY

TEMPLATE_RESPONSE="$(mktemp)"
ENDPOINT_RESPONSE="$(mktemp)"
trap 'rm -f "${TEMPLATE_RESPONSE}" "${ENDPOINT_RESPONSE}"' EXIT

echo "Creating RunPod serverless template..."
curl --fail-with-body -sS -X POST \
  "${RUNPOD_REST_ROOT}/templates" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  --data-binary "@${TEMPLATE_SRC}" > "${TEMPLATE_RESPONSE}"

TEMPLATE_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "${TEMPLATE_RESPONSE}")"
echo "Template ID: ${TEMPLATE_ID}"

python3 - "${ENDPOINT_SRC}" "${ENDPOINT_RESPONSE}" "${TEMPLATE_ID}" <<'PY'
import json
import sys

src, dest, template_id = sys.argv[1:]
with open(src, encoding="utf-8") as handle:
    payload = json.load(handle)
payload["templateId"] = template_id
with open(dest, "w", encoding="utf-8") as handle:
    json.dump(payload, handle)
PY

echo "Creating RunPod serverless endpoint..."
curl --fail-with-body -sS -X POST \
  "${RUNPOD_REST_ROOT}/endpoints" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  --data-binary "@${ENDPOINT_RESPONSE}" > "${TEMPLATE_RESPONSE}"

ENDPOINT_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "${TEMPLATE_RESPONSE}")"
python3 -m json.tool "${TEMPLATE_RESPONSE}"
echo
echo "RUNPOD_VOX_ENDPOINT_ID=${ENDPOINT_ID}"
echo "Add that value to .env, then select RunPod in the web UI."
