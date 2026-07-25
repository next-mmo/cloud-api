from __future__ import annotations

import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any

import soundfile as sf
from fastapi import FastAPI, HTTPException

from worker_base import fetch_uri, make_mock_wav, save_output, unwrap_job

app = FastAPI(title="VoxCPM2 Worker")
_model = None
_model_lock = Lock()


def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from voxcpm import VoxCPM
                _model = VoxCPM.from_pretrained(
                    os.getenv("MODEL_PATH", "openbmb/VoxCPM2"),
                    load_denoiser=os.getenv("LOAD_DENOISER", "false").lower() == "true",
                )
    return _model


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "engine": os.getenv("ENGINE_MODE", "mock")}


@app.get("/ready")
def ready() -> dict[str, str]:
    if os.getenv("ENGINE_MODE", "mock") == "real" and os.getenv("PRELOAD_MODEL", "1") == "1":
        get_model()
    return {"status": "ready"}


@app.post("/process")
def process(body: dict[str, Any]) -> dict[str, Any]:
    job = unwrap_job(body)
    job_id = str(job.get("job_id") or "tts-job")
    storage_provider = str(job.get("storage_provider") or "local")
    text = str(job.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text is required")

    with tempfile.TemporaryDirectory() as temp_dir:
        work = Path(temp_dir)
        reference = fetch_uri(job.get("reference_audio_uri"), storage_provider, work / "reference.wav")
        prompt_audio = fetch_uri(job.get("prompt_audio_uri"), storage_provider, work / "prompt.wav")
        output = work / f"{job_id}.wav"

        if os.getenv("ENGINE_MODE", "mock") == "real":
            model = get_model()
            designed_text = text
            if job.get("voice_description"):
                designed_text = f"({job['voice_description']}){text}"
            kwargs: dict[str, Any] = {
                "text": designed_text,
                "cfg_value": float(job.get("cfg_value", 2.0)),
                "inference_timesteps": int(job.get("inference_timesteps", 10)),
                "seed": int(job.get("seed", 42)),
            }
            if reference:
                kwargs["reference_wav_path"] = str(reference)
            if prompt_audio:
                kwargs["prompt_wav_path"] = str(prompt_audio)
                kwargs["prompt_text"] = str(job.get("prompt_text") or "")
            wav = model.generate(**kwargs)
            sf.write(output, wav, model.tts_model.sample_rate)
        else:
            make_mock_wav(output)

        stored = save_output(output, storage_provider, f"outputs/tts/{job_id}.wav")
        return {"job_id": job_id, "status": "succeeded", "kind": "tts", **stored}
