#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"

WORKER_URL="${CLORE_WORKER_URL:-${CUSTOM_WORKER_URL:-}}"
if [[ -z "${WORKER_URL}" ]]; then
  echo "Set CLORE_WORKER_URL (from wait-order.sh) or CUSTOM_WORKER_URL" >&2
  exit 1
fi
WORKER_URL="${WORKER_URL%/}"

TEXT="${1:-សួស្តី! នេះជាការសាកល្បងសំឡេងខ្មែរលើ Clore.ai។}"
JOB_ID_LOCAL="khmer-clore-$(date +%s)"
REQUEST_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "${REQUEST_FILE}" "${RESPONSE_FILE}"' EXIT

python3 - "${REQUEST_FILE}" "${JOB_ID_LOCAL}" "${TEXT}" <<'PY'
import json
import sys

path, job_id, text = sys.argv[1:]
payload = {
    "job_id": job_id,
    "kind": "tts",
    "storage_provider": "inline",
    "text": text,
    "cfg_value": 2.0,
    "inference_timesteps": 10,
    "seed": 42,
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False)
PY

echo "POST ${WORKER_URL}/process"
curl --fail-with-body -sS \
  -X POST "${WORKER_URL}/process" \
  -H "Content-Type: application/json" \
  --data-binary "@${REQUEST_FILE}" > "${RESPONSE_FILE}"

python3 -m json.tool "${RESPONSE_FILE}" >/dev/null

OUTPUT_FILE="${OUTPUT_FILE:-${JOB_ID_LOCAL}.wav}"
python3 - "${RESPONSE_FILE}" "${OUTPUT_FILE}" <<'PY'
import base64
import json
import sys

response_path, output_path = sys.argv[1:]
with open(response_path, encoding="utf-8") as handle:
    data = json.load(handle)
audio = data.get("audio_base64")
if not audio:
    raise SystemExit(json.dumps(data, indent=2, ensure_ascii=False))
with open(output_path, "wb") as handle:
    handle.write(base64.b64decode(audio))
print(f"Saved {output_path}")
PY

if command -v open >/dev/null 2>&1; then
  open "${OUTPUT_FILE}"
fi
