#!/usr/bin/env bash
set -euo pipefail
PORT="${PORT:-8000}"
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" &
APP_PID=$!

PIDS=("$APP_PID")

if [[ "${SALAD_QUEUE_WORKER_ENABLED:-0}" == "1" ]]; then
  /usr/local/bin/salad-http-job-queue-worker &
  PIDS+=("$!")
fi

if [[ "${RUNPOD_HANDLER_ENABLED:-0}" == "1" ]]; then
  python3 /app/runpod_handler.py &
  PIDS+=("$!")
fi

cleanup() {
  kill "${PIDS[@]}" 2>/dev/null || true
}
trap cleanup SIGTERM SIGINT

if [[ "${#PIDS[@]}" -gt 1 ]]; then
  wait -n "${PIDS[@]}"
else
  wait "$APP_PID"
fi
