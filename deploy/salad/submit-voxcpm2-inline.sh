#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./load-env.sh
source "${SCRIPT_DIR}/load-env.sh"
require_env SALAD_API_KEY SALAD_ORGANIZATION SALAD_PROJECT

QUEUE_NAME="${SALAD_VOX_QUEUE:-voxcpm2-jobs}"
TEXT="${1:-សួស្តី! នេះជាការសាកល្បងសំឡេងខ្មែរលើ SaladCloud។}"
JOB_ID_LOCAL="khmer-inline-$(date +%s)"
REQUEST_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "${REQUEST_FILE}" "${RESPONSE_FILE}"' EXIT

python3 - "${REQUEST_FILE}" "${JOB_ID_LOCAL}" "${TEXT}" <<'PY'
import json
import sys

path, job_id, text = sys.argv[1:]
payload = {
    "metadata": {"app_job_id": job_id, "kind": "tts"},
    "input": {
        "job_id": job_id,
        "kind": "tts",
        "storage_provider": "inline",
        "text": text,
        "cfg_value": 2.0,
        "inference_timesteps": 10,
        "seed": 42,
    },
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False)
PY

curl --fail-with-body -sS \
  -X POST "${SALAD_BASE}/queues/${QUEUE_NAME}/jobs" \
  -H "Salad-Api-Key: ${SALAD_API_KEY}" \
  -H "Content-Type: application/json" \
  --data-binary "@${REQUEST_FILE}" > "${RESPONSE_FILE}"

JOB_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "${RESPONSE_FILE}")"
echo "Submitted job ${JOB_ID}"

while true; do
  curl --fail-with-body -sS \
    "${SALAD_BASE}/queues/${QUEUE_NAME}/jobs/${JOB_ID}" \
    -H "Salad-Api-Key: ${SALAD_API_KEY}" > "${RESPONSE_FILE}"

  STATUS="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "${RESPONSE_FILE}")"
  echo "Status: ${STATUS}"

  case "${STATUS}" in
    succeeded|failed|cancelled) break ;;
  esac
  sleep 10
done

if [[ "${STATUS}" != "succeeded" ]]; then
  python3 -m json.tool "${RESPONSE_FILE}"
  exit 1
fi

OUTPUT_FILE="${OUTPUT_FILE:-${JOB_ID_LOCAL}.wav}"
python3 - "${RESPONSE_FILE}" "${OUTPUT_FILE}" <<'PY'
import base64
import json
import sys

response_path, output_path = sys.argv[1:]
with open(response_path, encoding="utf-8") as handle:
    data = json.load(handle)
output = data.get("output") or {}
audio = output.get("audio_base64")
if not audio:
    raise SystemExit(json.dumps(data, indent=2, ensure_ascii=False))
with open(output_path, "wb") as handle:
    handle.write(base64.b64decode(audio))
print(f"Saved {output_path}")
PY

if command -v open >/dev/null 2>&1; then
  open "${OUTPUT_FILE}"
fi
