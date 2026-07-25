from __future__ import annotations

import os


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default) or default


class Settings:
    """Process settings. Properties read os.environ live so the UI vault can override."""

    @property
    def database_url(self) -> str:
        return _env("DATABASE_URL", "sqlite:///./data/app.db")

    @property
    def cors_origins(self) -> tuple[str, ...]:
        return tuple(item.strip() for item in _env("CORS_ORIGINS", "http://localhost:5173").split(",") if item.strip())

    @property
    def vox_worker_url(self) -> str:
        return _env("VOX_WORKER_URL", "http://localhost:8011")

    @property
    def wan_worker_url(self) -> str:
        return _env("WAN_WORKER_URL", "http://localhost:8012")

    @property
    def custom_worker_url(self) -> str:
        return _env("CUSTOM_WORKER_URL")

    @property
    def custom_worker_token(self) -> str:
        return _env("CUSTOM_WORKER_TOKEN")

    @property
    def vast_worker_url(self) -> str:
        return _env("VAST_WORKER_URL") or _env("CUSTOM_WORKER_URL")

    @property
    def clore_worker_url(self) -> str:
        return _env("CLORE_WORKER_URL") or _env("CUSTOM_WORKER_URL")

    @property
    def salad_api_key(self) -> str:
        return _env("SALAD_API_KEY")

    @property
    def salad_organization(self) -> str:
        return _env("SALAD_ORGANIZATION")

    @property
    def salad_project(self) -> str:
        return _env("SALAD_PROJECT")

    @property
    def salad_vox_queue(self) -> str:
        return _env("SALAD_VOX_QUEUE", "voxcpm2-jobs")

    @property
    def salad_wan_queue(self) -> str:
        return _env("SALAD_WAN_QUEUE", "wangp-jobs")

    @property
    def salad_webhook_base_url(self) -> str:
        return _env("SALAD_WEBHOOK_BASE_URL")

    @property
    def runpod_api_key(self) -> str:
        return _env("RUNPOD_API_KEY")

    @property
    def runpod_vox_endpoint_id(self) -> str:
        return _env("RUNPOD_VOX_ENDPOINT_ID")

    @property
    def runpod_wan_endpoint_id(self) -> str:
        return _env("RUNPOD_WAN_ENDPOINT_ID")


settings = Settings()
