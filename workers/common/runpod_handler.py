"""RunPod Serverless queue handler that forwards jobs to the local FastAPI worker."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

import runpod

PORT = int(os.getenv("PORT", "8000"))
PROCESS_URL = os.getenv("RUNPOD_PROCESS_URL", f"http://127.0.0.1:{PORT}/process")
HEALTH_URL = os.getenv("RUNPOD_HEALTH_URL", f"http://127.0.0.1:{PORT}/health")
READY_TIMEOUT_SEC = int(os.getenv("RUNPOD_READY_TIMEOUT_SEC", "600"))


def _http_json(method: str, url: str, payload: dict | None = None, timeout: float | None = 60) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc


def _wait_for_worker() -> None:
    deadline = time.time() + READY_TIMEOUT_SEC
    last_error = "worker not reachable"
    while time.time() < deadline:
        try:
            _http_json("GET", HEALTH_URL, timeout=5)
            return
        except Exception as exc:  # noqa: BLE001 - retry until ready
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"Worker did not become healthy: {last_error}")


def handler(event: dict) -> dict:
    job_input = event.get("input") or {}
    if not isinstance(job_input, dict):
        raise ValueError("RunPod input must be a JSON object")

    _wait_for_worker()
    return _http_json("POST", PROCESS_URL, job_input, timeout=None)


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
