#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env CLORE_API_KEY

FILE="${1:?Usage: create-order.sh <order-json>}"
RESPONSE_FILE="$(mktemp)"
ORDER_PAYLOAD="$(mktemp)"
trap 'rm -f "${RESPONSE_FILE}" "${ORDER_PAYLOAD}"' EXIT

python3 - "${FILE}" "${ORDER_PAYLOAD}" "${CLORE_SERVER_ID:-}" <<'PY'
import json
import sys

src, dest, server_id = sys.argv[1:]
with open(src, encoding="utf-8") as handle:
    payload = json.load(handle)

if server_id.strip():
    payload["renting_server"] = int(server_id)

renting_server = int(payload.get("renting_server") or 0)
if renting_server <= 0:
    raise SystemExit(
        "renting_server is missing/invalid. Set CLORE_SERVER_ID or edit the order JSON."
    )

image = str(payload.get("image") or "")
if not image or "YOUR_DOCKERHUB_USER" in image or image.startswith("YOUR_"):
    raise SystemExit(f"Set a real Docker Hub image in the order JSON (got: {image!r})")

with open(dest, "w", encoding="utf-8") as handle:
    json.dump(payload, handle)
PY
FILE="${ORDER_PAYLOAD}"

curl --fail-with-body -sS -X POST \
  "${CLORE_API_ROOT}/create_order" \
  -H "auth: ${CLORE_API_KEY}" \
  -H "Content-Type: application/json" \
  --data-binary "@${FILE}" > "${RESPONSE_FILE}"

clore_check_code "${RESPONSE_FILE}"
python3 -m json.tool "${RESPONSE_FILE}"

ORDER_ID="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("order_id") or d.get("id") or "")' "${RESPONSE_FILE}")"
echo
echo "Order ID: ${ORDER_ID}"
echo "Poll with: ./deploy/clore/wait-order.sh ${ORDER_ID}"
