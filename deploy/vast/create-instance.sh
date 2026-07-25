#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env VAST_API_KEY

FILE="${1:?Usage: create-instance.sh <instance-json> [offer-id]}"
OFFER_ID="${2:-${VAST_OFFER_ID:-}}"
if [[ -z "${OFFER_ID}" ]]; then
  echo "Set VAST_OFFER_ID in .env, or pass offer id as the second argument." >&2
  echo "Find one with: ./deploy/vast/list-offers.sh 'RTX 4090'" >&2
  exit 1
fi

REQUEST_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "${REQUEST_FILE}" "${RESPONSE_FILE}"' EXIT

python3 - "${FILE}" "${REQUEST_FILE}" <<'PY'
import json
import os
import sys

src, dest = sys.argv[1:]
with open(src, encoding="utf-8") as handle:
    payload = json.load(handle)

image = str(payload.get("image") or "").strip()
env_image = os.environ.get("VOXCPM2_IMAGE", "").strip() or os.environ.get("VAST_IMAGE", "").strip()
if (not image or "YOUR_REGISTRY" in image or image.startswith("YOUR_")) and env_image:
    payload["image"] = env_image
    image = env_image

if not image or "YOUR_REGISTRY" in image or image.startswith("YOUR_"):
    raise SystemExit(
        "Set image in deploy/vast/instance-voxcpm2.json, or VOXCPM2_IMAGE / VAST_IMAGE in .env"
    )

# Optional private registry login from env: VAST_IMAGE_LOGIN='-u user -p token ghcr.io'
login = os.environ.get("VAST_IMAGE_LOGIN", "").strip()
if login:
    payload["image_login"] = login
elif image.startswith(("ghcr.io/", "gcr.io/", "registry.gitlab.com/")):
    raise SystemExit(
        "Private registry image requires VAST_IMAGE_LOGIN in .env.\n"
        "For GHCR create a classic PAT with read:packages, then set:\n"
        'VAST_IMAGE_LOGIN="-u YOUR_GITHUB_USER -p ghp_xxx ghcr.io"'
    )

print(f"Using image: {image}", file=sys.stderr)
with open(dest, "w", encoding="utf-8") as handle:
    json.dump(payload, handle)
PY

curl --fail-with-body -sS -X PUT \
  "${VAST_API_ROOT}/asks/${OFFER_ID}/" \
  -H "Authorization: Bearer ${VAST_API_KEY}" \
  -H "Content-Type: application/json" \
  --data-binary "@${REQUEST_FILE}" > "${RESPONSE_FILE}"

python3 -m json.tool "${RESPONSE_FILE}"

INSTANCE_ID="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("new_contract") or "")' "${RESPONSE_FILE}")"
SUCCESS="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(str(d.get("success", "")).lower())' "${RESPONSE_FILE}")"
if [[ "${SUCCESS}" != "true" || -z "${INSTANCE_ID}" ]]; then
  echo "Vast create failed" >&2
  exit 1
fi

echo
echo "Instance ID: ${INSTANCE_ID}"
echo "Add to .env: VAST_INSTANCE_ID=${INSTANCE_ID}"
echo "Then poll with: ./deploy/vast/wait-instance.sh ${INSTANCE_ID} 8011"
