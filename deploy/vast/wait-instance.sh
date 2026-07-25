#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env VAST_API_KEY

INSTANCE_ID="${1:?Usage: wait-instance.sh <instance-id> [http-port]}"
HTTP_PORT="${2:-8011}"
MAX_WAIT_SEC="${VAST_WAIT_TIMEOUT_SEC:-900}"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "${RESPONSE_FILE}"' EXIT

echo "Waiting for Vast instance ${INSTANCE_ID} (timeout ${MAX_WAIT_SEC}s)..."
START_TS="$(date +%s)"

while true; do
  NOW="$(date +%s)"
  if (( NOW - START_TS > MAX_WAIT_SEC )); then
    echo "Timed out waiting for instance ${INSTANCE_ID}" >&2
    exit 1
  fi

  curl --fail-with-body -sS \
    "${VAST_API_ROOT}/instances/${INSTANCE_ID}/" \
    -H "Authorization: Bearer ${VAST_API_KEY}" \
    -H "Accept: application/json" > "${RESPONSE_FILE}"

  set +e
  python3 - "${RESPONSE_FILE}" "${INSTANCE_ID}" "${HTTP_PORT}" <<'PY'
import json
import sys

path, instance_id, http_port = sys.argv[1:]
http_port = str(http_port)

with open(path, encoding="utf-8") as handle:
    data = json.load(handle)

inst = data.get("instances")
if isinstance(inst, list):
    match = None
    for item in inst:
        if str(item.get("id")) == str(instance_id):
            match = item
            break
    inst = match
elif isinstance(inst, dict) and "actual_status" not in inst and str(instance_id) in inst:
    inst = inst.get(str(instance_id)) or inst.get(int(instance_id))

if not isinstance(inst, dict):
    print("Status: not_found")
    raise SystemExit(2)

status = inst.get("actual_status") or inst.get("status") or "unknown"
print(f"Status: {status}")

bad = {"exited", "unknown", "offline", "error", "failed"}
if str(status).lower() in bad:
    print(json.dumps(inst, indent=2, ensure_ascii=False)[:4000])
    raise SystemExit(3)

if str(status).lower() != "running":
    raise SystemExit(2)

ports = inst.get("ports") or {}
host_port = None
for key in (f"{http_port}/tcp", str(http_port), f"{http_port}/udp"):
    value = ports.get(key)
    if isinstance(value, list) and value:
        first = value[0] or {}
        host_port = first.get("HostPort") or first.get("host_port")
        if host_port:
            break
    elif isinstance(value, (str, int)):
        host_port = value
        break

public_ip = inst.get("public_ipaddr") or inst.get("public_ip") or ""
# Some hosts only expose via mapped ports on public_ipaddr.
url = None
if public_ip and host_port:
    url = f"http://{public_ip}:{host_port}"

print(json.dumps(
    {
        "id": inst.get("id"),
        "actual_status": status,
        "public_ipaddr": public_ip,
        "ports": ports,
        "ssh_host": inst.get("ssh_host"),
        "ssh_port": inst.get("ssh_port"),
        "label": inst.get("label"),
    },
    indent=2,
    ensure_ascii=False,
))

if url:
    print(f"\nWorker URL: {url}")
    print("Add these lines to .env:")
    print(f"VAST_WORKER_URL={url}")
    print(f"VAST_INSTANCE_ID={instance_id}")
    print(f"CUSTOM_WORKER_URL={url}")
else:
    print("\nInstance is running but port mapping is not ready yet.")
    raise SystemExit(2)
PY
  STATUS_CODE=$?
  set -e

  if [[ "${STATUS_CODE}" -eq 0 ]]; then
    exit 0
  fi
  if [[ "${STATUS_CODE}" -eq 3 ]]; then
    echo "Instance entered a terminal failure state. Destroy it and retry another offer." >&2
    exit 1
  fi
  sleep 10
done
