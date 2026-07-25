#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env CLORE_API_KEY

GPU_FILTER="${1:-}"
MAX_USD_PER_HOUR="${CLORE_MAX_USD_PER_HOUR:-}"
MIN_RAM_GB="${CLORE_MIN_RAM_GB:-24}"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "${RESPONSE_FILE}"' EXIT

curl --fail-with-body -sS \
  "${CLORE_API_ROOT}/marketplace" \
  -H "auth: ${CLORE_API_KEY}" \
  -H "Accept: application/json" > "${RESPONSE_FILE}"

clore_check_code "${RESPONSE_FILE}"

python3 - "${RESPONSE_FILE}" "${GPU_FILTER}" "${MAX_USD_PER_HOUR}" "${MIN_RAM_GB}" <<'PY'
import json
import sys

path, gpu_filter, max_usd_raw, min_ram_raw = sys.argv[1:]
max_usd = float(max_usd_raw) if max_usd_raw.strip() else None
min_ram = float(min_ram_raw) if min_ram_raw.strip() else 0.0
gpu_filter = gpu_filter.strip().lower()

with open(path, encoding="utf-8") as handle:
    data = json.load(handle)

servers = data.get("servers") or []
rows = []
for server in servers:
    if server.get("rented"):
        continue
    specs = server.get("specs") or {}
    ram = float(specs.get("ram") or 0)
    if ram < min_ram:
        continue
    gpu_text = " ".join(server.get("gpu_array") or []) or str(specs.get("gpu") or "")
    if gpu_filter and gpu_filter not in gpu_text.lower():
        continue
    price = ((server.get("price") or {}).get("usd") or {})
    usd_hour = price.get("on_demand_clore") or price.get("on_demand")
    if max_usd is not None and usd_hour is not None and float(usd_hour) > max_usd:
        continue
    rows.append(
        {
            "id": server.get("id"),
            "gpu": gpu_text,
            "ram_gb": ram,
            "reliability": server.get("reliability"),
            "usd_per_hour": usd_hour,
            "allowed_coins": server.get("allowed_coins"),
        }
    )

rows.sort(key=lambda item: (item["usd_per_hour"] is None, item["usd_per_hour"] or 0))
print(json.dumps(rows[:50], indent=2))
print(f"\nShowing {min(len(rows), 50)} of {len(rows)} matching servers.", file=sys.stderr)
if rows:
    print(f"Pick a server id and set CLORE_SERVER_ID={rows[0]['id']} (cheapest match).", file=sys.stderr)
PY
