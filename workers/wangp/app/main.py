from __future__ import annotations

import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException

from worker_base import fetch_uri, save_output, unwrap_job

app = FastAPI(title="WanGP Worker")
_session = None
_session_lock = Lock()


def get_session():
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                from shared.api import init
                cli_args = [item.strip() for item in os.getenv("WANGP_CLI_ARGS", "--attention,sdpa,--profile,4").split(",") if item.strip()]
                _session = init(
                    root=Path(os.getenv("WANGP_ROOT", "/opt/Wan2GP")),
                    output_dir=Path(os.getenv("WANGP_OUTPUT_DIR", "/outputs")),
                    cli_args=cli_args,
                    console_output=True,
                )
    return _session


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "engine": "real"}


@app.get("/ready")
def ready() -> dict[str, str]:
    if os.getenv("PRELOAD_MODEL", "0") == "1":
        get_session()
    return {"status": "ready"}


@app.post("/process")
def process(body: dict[str, Any]) -> dict[str, Any]:
    job = unwrap_job(body)
    job_id = str(job.get("job_id") or "video-job")
    storage_provider = str(job.get("storage_provider") or "local")
    prompt = str(job.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(400, "prompt is required")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = Path(temp_dir)
            start_image = fetch_uri(job.get("start_image_uri"), storage_provider, work / "start.png")
            end_image = fetch_uri(job.get("end_image_uri"), storage_provider, work / "end.png")

            settings: dict[str, Any] = {
                "model_type": job.get("model_type", "ltx2_22B_distilled"),
                "prompt": prompt,
                "resolution": job.get("resolution", "720x1280"),
                "num_inference_steps": int(job.get("num_inference_steps", 8)),
                "video_length": int(job.get("video_length", 97)),
                "duration_seconds": float(job.get("duration_seconds", 4)),
                "force_fps": int(job.get("force_fps", 24)),
                "seed": int(job.get("seed", 42)),
            }
            if start_image:
                settings["image_start"] = str(start_image)
            if end_image:
                settings["image_end"] = str(end_image)
            settings.update(job.get("advanced_settings") or {})
            result = get_session().submit_task(settings).result()
            if not result.success or not result.generated_files:
                errors = [getattr(item, "message", str(item)) for item in result.errors]
                raise RuntimeError("WanGP generation failed: " + "; ".join(errors))
            output = Path(result.generated_files[0])

            stored = save_output(output, storage_provider, f"outputs/video/{job_id}{output.suffix or '.mp4'}")
            return {"job_id": job_id, "status": "succeeded", "kind": "video", **stored}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - surface inference failures to the client
        raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc
