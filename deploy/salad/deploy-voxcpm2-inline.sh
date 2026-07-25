#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env \
  SALAD_API_KEY \
  SALAD_ORGANIZATION \
  SALAD_PROJECT \
  SALAD_GPU_CLASS

IMAGE="${VOXCPM2_IMAGE:-ghcr.io/next-mmo/cloud-api-voxcpm2:inline-demo}"
GROUP_NAME="${SALAD_VOX_GROUP:-voxcpm2-inline-demo}"
QUEUE_NAME="${SALAD_VOX_QUEUE:-voxcpm2-jobs}"
PRIORITY="${SALAD_PRIORITY:-batch}"
MAX_PRICE="${SALAD_MAX_PRICE_PER_HOUR_USD:-}"
CONFIG_FILE="$(mktemp)"
trap 'rm -f "${CONFIG_FILE}"' EXIT

case "${PRIORITY}" in
  high|medium|low|batch) ;;
  *)
    echo "SALAD_PRIORITY must be high, medium, low, or batch" >&2
    exit 1
    ;;
esac

python3 - <<'PY'
import json
import os
import sys
import urllib.request

api_key = os.environ["SALAD_API_KEY"]
org = os.environ["SALAD_ORGANIZATION"]
gpu_id = os.environ["SALAD_GPU_CLASS"]
priority = os.getenv("SALAD_PRIORITY", "batch").lower()
max_price_raw = os.getenv("SALAD_MAX_PRICE_PER_HOUR_USD", "").strip()
url = f"https://api.salad.com/api/public/organizations/{org}/gpu-classes"
request = urllib.request.Request(
    url,
    headers={
        "Salad-Api-Key": api_key,
        "Accept": "application/json",
    },
)

with urllib.request.urlopen(request, timeout=60) as response:
    payload = json.load(response)

gpu = next((item for item in payload.get("items", []) if item.get("id") == gpu_id), None)
if gpu is None:
    raise SystemExit(f"GPU class {gpu_id} was not found for organization {org}")

prices = gpu.get("prices") or []
price_by_priority = {}
for entry in prices:
    level = str(entry.get("priority") or entry.get("name") or "").lower()
    value = entry.get("price")
    if level and value is not None:
        price_by_priority[level] = float(value)

if priority not in price_by_priority:
    print(json.dumps(gpu, indent=2), file=sys.stderr)
    raise SystemExit(
        f"Could not find {priority!r} pricing for GPU {gpu.get('name', gpu_id)}"
    )

hourly_price = price_by_priority[priority]
print(
    f"Selected GPU: {gpu.get('name', gpu_id)} | priority: {priority} | "
    f"price: US${hourly_price:.4f}/hour"
)

if max_price_raw:
    max_price = float(max_price_raw)
    if hourly_price > max_price:
        raise SystemExit(
            f"Deployment blocked: live price US${hourly_price:.4f}/hour exceeds "
            f"SALAD_MAX_PRICE_PER_HOUR_USD=US${max_price:.4f}"
        )
    print(f"Price guard passed: maximum US${max_price:.4f}/hour")
PY

python3 - "${CONFIG_FILE}" <<'PY'
import json
import os
import sys

config = {
    "name": os.getenv("SALAD_VOX_GROUP", "voxcpm2-inline-demo"),
    "display_name": "VoxCPM2 Inline Demo",
    "autostart_policy": True,
    "restart_policy": "always",
    "priority": os.getenv("SALAD_PRIORITY", "batch"),
    "container": {
        "image": os.getenv(
            "VOXCPM2_IMAGE",
            "ghcr.io/next-mmo/cloud-api-voxcpm2:inline-demo",
        ),
        "image_caching": True,
        "resources": {
            "cpu": int(os.getenv("SALAD_VOX_CPU", "4")),
            "memory": int(os.getenv("SALAD_VOX_MEMORY_MB", "32768")),
            "gpu_classes": [os.environ["SALAD_GPU_CLASS"]],
        },
        "environment_variables": {
            "ENGINE_MODE": "real",
            "MODEL_PATH": "/models/VoxCPM2",
            "PRELOAD_MODEL": "1",
            "LOAD_DENOISER": "false",
            "MAX_INLINE_AUDIO_BYTES": "7500000",
            "PORT": "8011",
            "SALAD_QUEUE_WORKER_ENABLED": "1",
            "SALAD_QUEUE_WORKER_LOG_LEVEL": "info",
        },
    },
    "replicas": 0,
    "startup_probe": {
        "http": {"path": "/health", "port": 8011},
        "initial_delay_seconds": 10,
        "period_seconds": 10,
        "timeout_seconds": 5,
        "failure_threshold": 60,
        "success_threshold": 1,
    },
    "readiness_probe": {
        "http": {"path": "/ready", "port": 8011},
        "initial_delay_seconds": 5,
        "period_seconds": 15,
        "timeout_seconds": 10,
        "failure_threshold": 60,
        "success_threshold": 1,
    },
    "queue_connection": {
        "path": "/process",
        "port": 8011,
        "queue_name": os.getenv("SALAD_VOX_QUEUE", "voxcpm2-jobs"),
    },
    "queue_autoscaler": {
        "min_replicas": 0,
        "max_replicas": 1,
        "desired_queue_length": 1,
        "polling_period": 30,
        "max_upscale_per_minute": 1,
        "max_downscale_per_minute": 1,
    },
}

with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(config, handle, indent=2)
PY

curl --fail-with-body -sS \
  -X POST "${SALAD_BASE}/containers" \
  -H "Salad-Api-Key: ${SALAD_API_KEY}" \
  -H "Content-Type: application/json" \
  --data-binary "@${CONFIG_FILE}"

echo
echo "Deployed ${GROUP_NAME} from ${IMAGE} using queue ${QUEUE_NAME} at ${PRIORITY} priority."
