#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env CLORE_API_KEY

ORDER_ID="${1:?Usage: wait-order.sh <order-id> [http-port]}"
HTTP_PORT="${2:-8011}"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "${RESPONSE_FILE}"' EXIT

echo "Waiting for Clore order ${ORDER_ID}..."
while true; do
  curl --fail-with-body -sS \
    "${CLORE_API_ROOT}/my_orders" \
    -H "auth: ${CLORE_API_KEY}" \
    -H "Accept: application/json" > "${RESPONSE_FILE}"
  clore_check_code "${RESPONSE_FILE}"

  if python3 - "${RESPONSE_FILE}" "${ORDER_ID}" "${HTTP_PORT}" <<'PY'
import json
import sys

path, order_id, http_port = sys.argv[1:]
order_id = int(order_id)
http_port = str(http_port)

with open(path, encoding="utf-8") as handle:
    data = json.load(handle)

match = None
for order in data.get("orders") or []:
    oid = order.get("order_id") or order.get("id")
    if oid is not None and int(oid) == order_id:
        match = order
        break

if match is None:
    print(f"Status: not_found")
    raise SystemExit(2)

status = str(match.get("status") or "unknown")
print(f"Status: {status}")
if status not in {"running", "active"}:
    raise SystemExit(2)

connection = match.get("connection") or {}
ports = connection.get("ports") or {}
raw = ports.get(http_port) or ports.get(str(http_port))
url = None
if isinstance(raw, str):
    if raw.startswith(("http://", "https://")):
        url = raw
    elif raw.startswith("tcp://"):
        url = "http://" + raw[len("tcp://") :]
    else:
        url = raw

print(json.dumps(match, indent=2, ensure_ascii=False))
if url:
    print(f"\nWorker URL: {url}")
    print(f"Use compute_provider=custom with CUSTOM_WORKER_URL={url}")
    print(f"export CLORE_WORKER_URL={url}")
else:
    print("\nNo HTTP mapping found for that port yet. Inspect connection.ports above.")
    raise SystemExit(2)
PY
  then
    exit 0
  fi
  sleep 8
done
