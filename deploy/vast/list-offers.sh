#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env VAST_API_KEY

GPU_NAME="${1:-${VAST_GPU_NAME:-RTX 4090}}"
MAX_USD="${VAST_MAX_USD_PER_HOUR:-}"
MIN_RAM_GB="${VAST_MIN_RAM_GB:-24}"
NUM_GPUS="${VAST_NUM_GPUS:-1}"
LIMIT="${VAST_OFFER_LIMIT:-10}"
REQUEST_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "${REQUEST_FILE}" "${RESPONSE_FILE}"' EXIT

python3 - "${REQUEST_FILE}" "${GPU_NAME}" "${NUM_GPUS}" "${LIMIT}" "${MAX_USD}" "${MIN_RAM_GB}" <<'PY'
import json
import sys

path, gpu_name, num_gpus, limit, max_usd, min_ram = sys.argv[1:]
query = {
    "verified": {"eq": True},
    "rentable": {"eq": True},
    "rented": {"eq": False},
    "gpu_name": {"eq": gpu_name},
    "num_gpus": {"eq": int(num_gpus)},
    "direct_port_count": {"gte": 1},
    "cpu_ram": {"gte": float(min_ram) * 1024},
    "order": [["dph_total", "asc"]],
    "type": "on-demand",
    "limit": int(limit),
}
if max_usd.strip():
    query["dph_total"] = {"lte": float(max_usd)}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(query, handle)
PY

curl --fail-with-body -sS -X POST \
  "${VAST_API_ROOT}/bundles/" \
  -H "Authorization: Bearer ${VAST_API_KEY}" \
  -H "Content-Type: application/json" \
  --data-binary "@${REQUEST_FILE}" > "${RESPONSE_FILE}"

python3 - "${RESPONSE_FILE}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)

offers = data.get("offers") or data.get("bundles") or []
rows = []
for offer in offers:
    rows.append(
        {
            "id": offer.get("id"),
            "gpu_name": offer.get("gpu_name"),
            "num_gpus": offer.get("num_gpus"),
            "cpu_ram_gb": round(float(offer.get("cpu_ram") or 0) / 1024, 1),
            "disk_gb": offer.get("disk_space"),
            "usd_per_hour": offer.get("dph_total"),
            "reliability": offer.get("reliability"),
            "geolocation": offer.get("geolocation"),
            "inet_down": offer.get("inet_down"),
            "inet_up": offer.get("inet_up"),
        }
    )

print(json.dumps(rows, indent=2))
if rows:
    print(f"\nCheapest match — add to .env:\nVAST_OFFER_ID={rows[0]['id']}", file=sys.stderr)
else:
    print("No matching offers. Relax VAST_MAX_USD_PER_HOUR / GPU filters.", file=sys.stderr)
PY
