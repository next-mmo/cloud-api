from __future__ import annotations

from pathlib import Path
from typing import Any

from nd_gpu_common import StorageFactory


def unwrap_job(body: dict[str, Any]) -> dict[str, Any]:
    value = body.get("input", body)
    if not isinstance(value, dict):
        raise ValueError("Job input must be a JSON object")
    return value


def fetch_uri(uri: str | None, provider: str, destination: Path) -> Path | None:
    if not uri:
        return None
    if uri.startswith(("http://", "https://")):
        import urllib.request
        destination.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(uri, destination)
        return destination
    return StorageFactory.create(provider).download(uri, destination)


def save_output(local_path: Path, storage_provider: str, object_name: str) -> dict[str, Any]:
    stored = StorageFactory.create(storage_provider).upload(local_path, object_name)
    return {
        "output_uri": stored.uri,
        "public_url": stored.public_url,
        "storage_provider": stored.provider,
    }
