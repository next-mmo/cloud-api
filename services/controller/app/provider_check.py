from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

import httpx

from .config import settings


def _configured(*names: str) -> bool:
    return all(bool((os.getenv(name) or "").strip()) for name in names)


def _missing(names: list[str]) -> list[str]:
    return [name for name in names if not (os.getenv(name) or "").strip()]


def _valid_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


async def _probe_health(url: str) -> tuple[bool, str]:
    target = url.rstrip("/") + "/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(target)
        if response.status_code == 200:
            return True, "Worker health check passed"
        return False, f"Worker health returned HTTP {response.status_code}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Worker unreachable at {target}: {exc}"


def _http_worker_ready(*env_names: str) -> bool:
    return any(_configured(name) for name in env_names)


def capability_snapshot() -> dict[str, Any]:
    local_ready = _configured("VOX_WORKER_URL") and _configured("WAN_WORKER_URL")
    custom_ready = _configured("CUSTOM_WORKER_URL")
    vast_ready = _http_worker_ready("VAST_WORKER_URL", "CUSTOM_WORKER_URL")
    clore_ready = _http_worker_ready("CLORE_WORKER_URL", "CUSTOM_WORKER_URL")
    salad_ready = _configured("SALAD_API_KEY", "SALAD_ORGANIZATION", "SALAD_PROJECT")
    runpod_ready = _configured("RUNPOD_API_KEY") and (
        _configured("RUNPOD_VOX_ENDPOINT_ID") or _configured("RUNPOD_WAN_ENDPOINT_ID")
    )
    r2_ready = _configured("S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")
    drive_ready = _configured("GOOGLE_DRIVE_REFRESH_TOKEN")
    return {
        "compute": {
            "local": local_ready,
            "salad": salad_ready,
            "runpod": runpod_ready,
            "vast": vast_ready,
            "clore": clore_ready,
            "custom": custom_ready,
        },
        "storage": {
            "local": True,
            "r2": r2_ready,
            "google_drive": drive_ready,
        },
        "missing": {
            "local": _missing(["VOX_WORKER_URL", "WAN_WORKER_URL"]),
            "custom": _missing(["CUSTOM_WORKER_URL"]),
            "vast": [] if vast_ready else ["VAST_WORKER_URL"],
            "clore": [] if clore_ready else ["CLORE_WORKER_URL"],
            "salad": _missing(["SALAD_API_KEY", "SALAD_ORGANIZATION", "SALAD_PROJECT"]),
            "runpod": _missing(["RUNPOD_API_KEY", "RUNPOD_VOX_ENDPOINT_ID", "RUNPOD_WAN_ENDPOINT_ID"]),
            "r2": _missing(["S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"]),
            "google_drive": _missing(["GOOGLE_DRIVE_REFRESH_TOKEN"]),
        },
    }


def _effective_worker_url(compute: str, custom_worker_url: str | None) -> str:
    override = (custom_worker_url or "").strip()
    if override:
        return override
    if compute == "vast":
        return (settings.vast_worker_url or "").strip()
    if compute == "clore":
        return (settings.clore_worker_url or "").strip()
    if compute == "custom":
        return (settings.custom_worker_url or "").strip()
    return ""


async def _check_http_worker(
    *,
    label: str,
    secrets_hint: str,
    url: str,
    probe_worker: bool,
    issues: list[str],
) -> str | None:
    if not url:
        issues.append(f"{label} URL is required ({secrets_hint}).")
        return None
    if not _valid_http_url(url):
        issues.append(f"{label} URL must be a valid http(s) URL.")
        return None
    if not probe_worker:
        return None
    ok, message = await _probe_health(url)
    if not ok:
        issues.append(message)
        return "unreachable"
    return "ok"


async def check_providers(
    compute_provider: str,
    storage_provider: str,
    custom_worker_url: str | None = None,
    *,
    probe_worker: bool = True,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    worker_health: str | None = None
    caps = capability_snapshot()
    compute = compute_provider.lower()
    storage = storage_provider.lower()

    effective_custom = _effective_worker_url(compute, custom_worker_url)

    if compute in {"custom", "vast", "clore"}:
        if compute == "vast":
            worker_health = await _check_http_worker(
                label="Vast.ai worker",
                secrets_hint="enter it here or save VAST_WORKER_URL in Secrets",
                url=effective_custom,
                probe_worker=probe_worker,
                issues=issues,
            )
            if not _configured("VAST_API_KEY"):
                warnings.append("VAST_API_KEY is not in Secrets — deploy scripts need it, but jobs only need the worker URL.")
        elif compute == "clore":
            worker_health = await _check_http_worker(
                label="Clore.ai worker",
                secrets_hint="enter it here or save CLORE_WORKER_URL in Secrets",
                url=effective_custom,
                probe_worker=probe_worker,
                issues=issues,
            )
            if not _configured("CLORE_API_KEY"):
                warnings.append("CLORE_API_KEY is not in Secrets — deploy scripts need it, but jobs only need the worker URL.")
        else:
            worker_health = await _check_http_worker(
                label="Custom worker",
                secrets_hint="enter it here or save CUSTOM_WORKER_URL in Secrets",
                url=effective_custom,
                probe_worker=probe_worker,
                issues=issues,
            )
    elif compute == "local":
        missing = caps["missing"]["local"]
        if missing:
            issues.append(f"Local workers need Secrets: {', '.join(missing)}.")
        elif probe_worker:
            for label, url in (
                ("VoxCPM2", settings.vox_worker_url),
                ("WanGP", settings.wan_worker_url),
            ):
                ok, message = await _probe_health(url)
                if not ok:
                    issues.append(f"{label}: {message}")
                    worker_health = "unreachable"
            if worker_health is None:
                worker_health = "ok"
    elif compute == "salad":
        missing = caps["missing"]["salad"]
        if missing:
            issues.append(f"SaladCloud needs Secrets: {', '.join(missing)}.")
    elif compute == "runpod":
        if not _configured("RUNPOD_API_KEY"):
            issues.append("RunPod needs Secrets: RUNPOD_API_KEY.")
        if not _configured("RUNPOD_VOX_ENDPOINT_ID") and not _configured("RUNPOD_WAN_ENDPOINT_ID"):
            issues.append("RunPod needs at least one endpoint ID (VOX or WAN) in Secrets.")
        elif not _configured("RUNPOD_VOX_ENDPOINT_ID"):
            warnings.append("RUNPOD_VOX_ENDPOINT_ID is missing — TTS jobs will fail until it is set.")
        elif not _configured("RUNPOD_WAN_ENDPOINT_ID"):
            warnings.append("RUNPOD_WAN_ENDPOINT_ID is missing — video jobs will fail until it is set.")
    else:
        issues.append(f"Unsupported compute provider: {compute_provider}")

    if storage == "local":
        pass
    elif storage == "r2":
        missing = caps["missing"]["r2"]
        if missing:
            issues.append(f"R2 / S3 needs Secrets: {', '.join(missing)}.")
    elif storage == "google_drive":
        if not _configured("GOOGLE_DRIVE_REFRESH_TOKEN"):
            issues.append("Google Drive is not connected. Open Secrets → Google Drive → Connect with Google.")
    else:
        issues.append(f"Unsupported storage provider: {storage_provider}")

    storage_issue_prefixes = ("R2 / S3", "Google Drive", "Unsupported storage")
    storage_ready = not any(issue.startswith(storage_issue_prefixes) for issue in issues)
    compute_ready = not any(not issue.startswith(storage_issue_prefixes) for issue in issues)

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "compute_ready": compute_ready,
        "storage_ready": storage_ready,
        "worker_health": worker_health,
        "capabilities": caps,
        "effective_custom_worker_url": effective_custom or None,
        "secrets_path": "/settings",
    }
