from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl

ComputeProvider = Literal["mock", "local", "salad", "runpod", "custom"]
StorageProvider = Literal["local", "r2", "google_drive"]


class ProviderSelection(BaseModel):
    compute_provider: ComputeProvider = "mock"
    storage_provider: StorageProvider = "local"
    custom_worker_url: str | None = None


class TTSRequest(ProviderSelection):
    text: str = Field(min_length=1, max_length=20000)
    reference_audio_uri: str | None = None
    prompt_audio_uri: str | None = None
    prompt_text: str | None = None
    voice_description: str | None = None
    cfg_value: float = Field(default=2.0, ge=0.1, le=10)
    inference_timesteps: int = Field(default=10, ge=1, le=100)
    seed: int = Field(default=42, ge=0)


class VideoRequest(ProviderSelection):
    prompt: str = Field(min_length=1, max_length=10000)
    model_type: str = "ltx2_22B_distilled"
    start_image_uri: str | None = None
    end_image_uri: str | None = None
    resolution: str = "720x1280"
    video_length: int = Field(default=97, ge=1, le=2000)
    duration_seconds: float = Field(default=4, gt=0, le=300)
    force_fps: int = Field(default=24, ge=1, le=120)
    num_inference_steps: int = Field(default=8, ge=1, le=200)
    seed: int = Field(default=42, ge=0)
    advanced_settings: dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    id: str
    kind: str
    compute_provider: str
    storage_provider: str
    status: str
    provider_job_id: str | None
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    uri: str
    public_url: str | None
    provider: str
    name: str


class CapabilityResponse(BaseModel):
    compute: dict[str, bool]
    storage: dict[str, bool]
