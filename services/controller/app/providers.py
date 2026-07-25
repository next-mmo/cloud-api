from __future__ import annotations

import asyncio
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


class MockProvider:
    async def submit(self, kind: str, job_id: str, payload: dict[str, Any]) -> Submission:
        await asyncio.sleep(0.05)
        return Submission(
            provider_job_id=f"mock-{job_id}",
            status="succeeded",
            result={
                "job_id": job_id,
                "status": "succeeded",
                "message": f"Mock {kind} job completed. Switch to Local, Salad, RunPod, or Custom for GPU inference.",
                "output_uri": None,
                "public_url": None,
            },
        )

    async def poll(self, kind: str, provider_job_id: str) -> Submission:
        return Submission(provider_job_id=provider_job_id, status="succeeded")


class DirectHTTPProvider:
    def __init__(self, worker_url: str, token: str = "") -> None:
        self.worker_url = worker_url.rstrip("/")
        self.token = token

    async def submit(self, kind: str, job_id: str, payload: dict[str, Any]) -> Submission:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                f"{self.worker_url}/process",
                json={"job_id": job_id, "kind": kind, **payload},
                headers=headers,
            )
        if response.is_error:
            raise ProviderError(f"Worker returned {response.status_code}: {response.text[:800]}")
        result = response.json()
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
    if selected == "mock":
        return MockProvider()
    if selected == "local":
        return DirectHTTPProvider(settings.vox_worker_url if kind == "tts" else settings.wan_worker_url)
    if selected == "salad":
        return SaladProvider()
    if selected == "runpod":
        return RunPodProvider()
    if selected == "custom":
        url = custom_url or settings.custom_worker_url
        if not url:
            raise ProviderError("Custom worker URL is missing")
        return DirectHTTPProvider(url, settings.custom_worker_token)
    raise ProviderError(f"Unsupported compute provider: {name}")
