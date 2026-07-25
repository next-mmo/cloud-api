#!/usr/bin/env bash
set -euo pipefail
PORT="${PORT:-8000}"
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" &
APP_PID=$!

if [[ "${SALAD_QUEUE_WORKER_ENABLED:-0}" == "1" ]]; then
  /usr/local/bin/salad-http-job-queue-worker &
  QUEUE_PID=$!
  trap 'kill $APP_PID $QUEUE_PID 2>/dev/null || true' SIGTERM SIGINT
  wait -n "$APP_PID" "$QUEUE_PID"
else
  trap 'kill $APP_PID 2>/dev/null || true' SIGTERM SIGINT
  wait "$APP_PID"
fi
