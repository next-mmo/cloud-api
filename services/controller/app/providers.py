from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from .config import settings


@dataclass(slots=True)
class Submission:
    provider_job_id: str | None
    status: str
    result: dict[str, Any] | None = None


class ProviderError(RuntimeError):
    pass


class DirectHTTPProvider:
    def __init__(self, worker_url: str, token: str = "") -> None:
        self.worker_url = worker_url.rstrip("/")
        self.token = token

    def _materialize_inline_result(self, kind: str, job_id: str, result: dict[str, Any]) -> dict[str, Any]:
        """Save inline base64 media onto the controller so the web UI can open it."""
        import base64
        import tempfile
        from pathlib import Path

        from nd_gpu_common import StorageFactory

        audio_b64 = result.get("audio_base64")
        video_b64 = result.get("video_base64")
        if not audio_b64 and not video_b64:
            return result

        suffix = ".wav" if audio_b64 else ".mp4"
        raw = base64.b64decode(audio_b64 or video_b64)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            tmp_path = Path(tmp.name)
        try:
            stored = StorageFactory.create("local").upload(
                tmp_path,
                f"outputs/{kind}/{job_id}{suffix}",
            )
        finally:
            tmp_path.unlink(missing_ok=True)

        cleaned = {
            key: value
            for key, value in result.items()
            if key not in {"audio_base64", "video_base64"}
        }
        cleaned.update(
            {
                "output_uri": stored.uri,
                "public_url": stored.public_url,
                "storage_provider": stored.provider,
            }
        )
        return cleaned

    async def submit(self, kind: str, job_id: str, payload: dict[str, Any]) -> Submission:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        worker_payload = dict(payload)
        # Remote GPU workers cannot serve controller "local" files; return inline media instead.
        if str(worker_payload.get("storage_provider") or "local").lower() == "local":
            worker_payload["storage_provider"] = "inline"
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                f"{self.worker_url}/process",
                json={"job_id": job_id, "kind": kind, **worker_payload},
                headers=headers,
            )
        if response.is_error:
            raise ProviderError(f"Worker returned {response.status_code}: {response.text[:800]}")
        result = response.json()
        if result.get("status", "succeeded") == "succeeded":
            result = self._materialize_inline_result(kind, job_id, result)
        return Submission(
            provider_job_id=result.get("job_id", job_id),
            status=result.get("status", "succeeded"),
            result=result,
        )

    async def poll(self, kind: str, provider_job_id: str) -> Submission:
        return Submission(provider_job_id=provider_job_id, status="succeeded")


class SaladProvider:
    base_url = "https://api.salad.com/api/public"

    def _queue(self, kind: str) -> str:
        return settings.salad_vox_queue if kind == "tts" else settings.salad_wan_queue

    def _headers(self) -> dict[str, str]:
        if not settings.salad_api_key:
            raise ProviderError("SALAD_API_KEY is not configured")
        return {"Salad-Api-Key": settings.salad_api_key, "Content-Type": "application/json"}

    def _jobs_url(self, kind: str) -> str:
        if not settings.salad_organization or not settings.salad_project:
            raise ProviderError("SALAD_ORGANIZATION and SALAD_PROJECT are required")
        return (
            f"{self.base_url}/organizations/{settings.salad_organization}"
            f"/projects/{settings.salad_project}/queues/{self._queue(kind)}/jobs"
        )

    async def submit(self, kind: str, job_id: str, payload: dict[str, Any]) -> Submission:
        body: dict[str, Any] = {"metadata": {"app_job_id": job_id, "kind": kind}, "input": {"job_id": job_id, "kind": kind, **payload}}
        if settings.salad_webhook_base_url:
            body["webhook"] = f"{settings.salad_webhook_base_url.rstrip('/')}/api/webhooks/salad"
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(self._jobs_url(kind), json=body, headers=self._headers())
        if response.is_error:
            raise ProviderError(f"Salad returned {response.status_code}: {response.text[:800]}")
        data = response.json()
        return Submission(provider_job_id=data["id"], status=data.get("status", "pending"), result=None)

    async def poll(self, kind: str, provider_job_id: str) -> Submission:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(f"{self._jobs_url(kind)}/{provider_job_id}", headers=self._headers())
        if response.is_error:
            raise ProviderError(f"Salad status returned {response.status_code}: {response.text[:800]}")
        data = response.json()
        status = data.get("status", "pending")
        result = data.get("output") if status == "succeeded" else None
        error = data.get("error") or data.get("events") if status == "failed" else None
        if error and result is None:
            result = {"error": error}
        return Submission(provider_job_id=provider_job_id, status=status, result=result)


class RunPodProvider:
    base_url = "https://api.runpod.ai/v2"

    def _endpoint_id(self, kind: str) -> str:
        endpoint = settings.runpod_vox_endpoint_id if kind == "tts" else settings.runpod_wan_endpoint_id
        if not endpoint:
            raise ProviderError(f"RunPod endpoint for {kind} is not configured")
        return endpoint

    def _headers(self) -> dict[str, str]:
        if not settings.runpod_api_key:
            raise ProviderError("RUNPOD_API_KEY is not configured")
        return {"Authorization": f"Bearer {settings.runpod_api_key}", "Content-Type": "application/json"}

    async def submit(self, kind: str, job_id: str, payload: dict[str, Any]) -> Submission:
        endpoint = self._endpoint_id(kind)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/{endpoint}/run",
                json={"input": {"job_id": job_id, "kind": kind, **payload}},
                headers=self._headers(),
            )
        if response.is_error:
            raise ProviderError(f"RunPod returned {response.status_code}: {response.text[:800]}")
        data = response.json()
        return Submission(provider_job_id=data.get("id"), status="pending")

    async def poll(self, kind: str, provider_job_id: str) -> Submission:
        endpoint = self._endpoint_id(kind)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"{self.base_url}/{endpoint}/status/{provider_job_id}",
                headers=self._headers(),
            )
        if response.is_error:
            raise ProviderError(f"RunPod status returned {response.status_code}: {response.text[:800]}")
        data = response.json()
        mapped = {
            "IN_QUEUE": "pending",
            "IN_PROGRESS": "running",
            "COMPLETED": "succeeded",
            "FAILED": "failed",
            "CANCELLED": "cancelled",
            "TIMED_OUT": "failed",
        }.get(data.get("status"), "pending")
        return Submission(provider_job_id=provider_job_id, status=mapped, result=data.get("output"))


def get_provider(name: str, kind: str, custom_url: str | None = None):
    selected = name.lower()
    if selected == "local":
        return DirectHTTPProvider(settings.vox_worker_url if kind == "tts" else settings.wan_worker_url)
    if selected == "salad":
        return SaladProvider()
    if selected == "runpod":
        return RunPodProvider()
    if selected in {"custom", "vast", "clore"}:
        if selected == "vast":
            url = custom_url or settings.vast_worker_url
            label = "Vast.ai worker URL (VAST_WORKER_URL)"
        elif selected == "clore":
            url = custom_url or settings.clore_worker_url
            label = "Clore.ai worker URL (CLORE_WORKER_URL)"
        else:
            url = custom_url or settings.custom_worker_url
            label = "Custom worker URL"
        if not url:
            raise ProviderError(f"{label} is missing")
        return DirectHTTPProvider(url, settings.custom_worker_token)
    raise ProviderError(f"Unsupported compute provider: {name}")
