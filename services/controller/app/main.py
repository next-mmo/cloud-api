from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from nd_gpu_common import StorageFactory

from .config import settings
from .db import JobRecord, SessionLocal, get_db, init_db
from .providers import ProviderError, get_provider
from .schemas import (
    CapabilityResponse,
    JobResponse,
    ProviderCheckRequest,
    SettingsEnvUploadRequest,
    SettingsUpdateRequest,
    TTSRequest,
    UploadResponse,
    VideoRequest,
)
from .google_drive_oauth import get_oauth_status, start_oauth
from .provider_check import capability_snapshot, check_providers
from .secret_vault import (
    VaultError,
    apply_vault_to_environ,
    load_vault,
    merge_updates,
    parse_env_text,
    public_status,
    save_vault,
)
from .settings_catalog import schema_payload

app = FastAPI(title="WanGP + VoxCPM2 Cloud Controller", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

local_storage_root = Path(os.getenv("LOCAL_STORAGE_DIR", "./data/files")).resolve()
local_storage_root.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(local_storage_root)), name="files")


@app.on_event("startup")
def startup() -> None:
    init_db()
    db = SessionLocal()
    try:
        try:
            apply_vault_to_environ(load_vault(db))
        except VaultError:
            # Host key missing or vault unreadable — keep process env only.
            apply_vault_to_environ({})
    finally:
        db.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/capabilities", response_model=CapabilityResponse)
def capabilities() -> CapabilityResponse:
    snap = capability_snapshot()
    return CapabilityResponse(compute=snap["compute"], storage=snap["storage"], missing=snap["missing"])


@app.post("/api/providers/check")
async def providers_check(body: ProviderCheckRequest) -> dict[str, Any]:
    return await check_providers(
        body.compute_provider,
        body.storage_provider,
        body.custom_worker_url,
        probe_worker=body.probe_worker,
    )


@app.get("/api/settings/schema")
def settings_schema() -> dict[str, Any]:
    return schema_payload()


@app.get("/api/settings")
def get_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        values = load_vault(db)
    except VaultError as exc:
        raise HTTPException(503, str(exc)) from exc
    return public_status(values)


@app.put("/api/settings")
def put_settings(body: SettingsUpdateRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        current = load_vault(db)
        merged = merge_updates(current, body.values)
        saved = save_vault(db, merged)
    except VaultError as exc:
        raise HTTPException(503, str(exc)) from exc
    return public_status(saved)


@app.post("/api/settings/env")
def upload_settings_env(body: SettingsEnvUploadRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    parsed = parse_env_text(body.content)
    if not parsed:
        raise HTTPException(400, "No recognized provider keys found in .env content")
    try:
        current = {} if body.replace else load_vault(db)
        merged = {**current, **parsed}
        saved = save_vault(db, merged)
    except VaultError as exc:
        raise HTTPException(503, str(exc)) from exc
    return public_status(saved)


@app.delete("/api/settings")
def clear_settings(db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        saved = save_vault(db, {})
    except VaultError as exc:
        raise HTTPException(503, str(exc)) from exc
    return public_status(saved)


@app.post("/api/settings/google-drive/connect")
def google_drive_connect() -> dict[str, Any]:
    """Start rclone-style Google Drive OAuth (no Cloud Console app required)."""
    try:
        return start_oauth()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/settings/google-drive/connect")
def google_drive_connect_status() -> dict[str, Any]:
    return get_oauth_status()


def create_job(db: Session, kind: str, payload: dict[str, Any]) -> JobRecord:
    job = JobRecord(
        id=uuid.uuid4().hex,
        kind=kind,
        compute_provider=payload["compute_provider"],
        storage_provider=payload["storage_provider"],
        status="submitting",
        payload=payload,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


async def submit_job(job_id: str) -> None:
    from .db import SessionLocal

    db = SessionLocal()
    try:
        job = db.get(JobRecord, job_id)
        if not job:
            return
        provider = get_provider(job.compute_provider, job.kind, job.payload.get("custom_worker_url"))
        submission = await provider.submit(job.kind, job.id, job.payload)
        job.provider_job_id = submission.provider_job_id
        job.status = submission.status
        job.result = submission.result
        db.commit()
    except Exception as exc:
        job = db.get(JobRecord, job_id)
        if job:
            job.status = "failed"
            job.error = str(exc)
            db.commit()
    finally:
        db.close()


@app.post("/api/jobs/tts", response_model=JobResponse)
async def create_tts_job(body: TTSRequest, background: BackgroundTasks, db: Session = Depends(get_db)) -> JobRecord:
    job = create_job(db, "tts", body.model_dump())
    background.add_task(submit_job, job.id)
    return job


@app.post("/api/jobs/video", response_model=JobResponse)
async def create_video_job(body: VideoRequest, background: BackgroundTasks, db: Session = Depends(get_db)) -> JobRecord:
    job = create_job(db, "video", body.model_dump())
    background.add_task(submit_job, job.id)
    return job


@app.get("/api/jobs", response_model=list[JobResponse])
def list_jobs(db: Session = Depends(get_db)) -> list[JobRecord]:
    return list(db.scalars(select(JobRecord).order_by(desc(JobRecord.created_at)).limit(100)))


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: Session = Depends(get_db)) -> JobRecord:
    job = db.get(JobRecord, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status in {"pending", "running"} and job.provider_job_id:
        try:
            provider = get_provider(job.compute_provider, job.kind, job.payload.get("custom_worker_url"))
            update = await provider.poll(job.kind, job.provider_job_id)
            job.status = update.status
            if update.result is not None:
                job.result = update.result
            db.commit()
            db.refresh(job)
        except ProviderError as exc:
            job.error = str(exc)
            db.commit()
    return job


@app.post("/api/uploads", response_model=UploadResponse)
async def upload(
    file: Annotated[UploadFile, File()],
    storage_provider: Annotated[str, Form()] = "local",
) -> UploadResponse:
    suffix = Path(file.filename or "upload.bin").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        while chunk := await file.read(1024 * 1024):
            tmp.write(chunk)
        temp_path = Path(tmp.name)
    try:
        storage = StorageFactory.create(storage_provider)
        stored = storage.upload(temp_path, f"uploads/{uuid.uuid4().hex}-{file.filename or 'upload.bin'}")
        return UploadResponse(
            uri=stored.uri,
            public_url=stored.public_url,
            provider=stored.provider,
            name=file.filename or "upload.bin",
        )
    except Exception as exc:
        raise HTTPException(500, f"Upload failed: {exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/api/webhooks/salad")
async def salad_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    # For production, validate webhook-signature with SALAD_WEBHOOK_SECRET + svix.
    payload = await request.json()
    metadata = payload.get("metadata") or {}
    app_job_id = metadata.get("app_job_id")
    if app_job_id:
        job = db.get(JobRecord, app_job_id)
        if job:
            job.status = payload.get("status", job.status)
            output = payload.get("output", payload.get("result"))
            if output is not None:
                job.result = output
            db.commit()
    return {"ok": True}
