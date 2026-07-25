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
CONFIG_FILE="$(mktemp)"
trap 'rm -f "${CONFIG_FILE}"' EXIT

python3 - "${CONFIG_FILE}" <<'PY'
import json
import os
import sys

config = {
    "name": os.getenv("SALAD_VOX_GROUP", "voxcpm2-inline-demo"),
    "display_name": "VoxCPM2 Inline Demo",
    "autostart_policy": True,
    "restart_policy": "always",
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
echo "Deployed ${GROUP_NAME} from ${IMAGE} using queue ${QUEUE_NAME}."
