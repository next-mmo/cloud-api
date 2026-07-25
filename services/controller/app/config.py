from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    cors_origins: tuple[str, ...] = tuple(
        item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if item.strip()
    )
    vox_worker_url: str = os.getenv("VOX_WORKER_URL", "http://localhost:8011")
    wan_worker_url: str = os.getenv("WAN_WORKER_URL", "http://localhost:8012")
    custom_worker_url: str = os.getenv("CUSTOM_WORKER_URL", "")
    custom_worker_token: str = os.getenv("CUSTOM_WORKER_TOKEN", "")
    salad_api_key: str = os.getenv("SALAD_API_KEY", "")
    salad_organization: str = os.getenv("SALAD_ORGANIZATION", "")
    salad_project: str = os.getenv("SALAD_PROJECT", "")
    salad_vox_queue: str = os.getenv("SALAD_VOX_QUEUE", "voxcpm2-jobs")
    salad_wan_queue: str = os.getenv("SALAD_WAN_QUEUE", "wangp-jobs")
    salad_webhook_base_url: str = os.getenv("SALAD_WEBHOOK_BASE_URL", "")
    runpod_api_key: str = os.getenv("RUNPOD_API_KEY", "")
    runpod_vox_endpoint_id: str = os.getenv("RUNPOD_VOX_ENDPOINT_ID", "")
    runpod_wan_endpoint_id: str = os.getenv("RUNPOD_WAN_ENDPOINT_ID", "")


settings = Settings()
