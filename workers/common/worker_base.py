from __future__ import annotations

import math
import os
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

from nd_gpu_common import StorageFactory


def unwrap_job(body: dict[str, Any]) -> dict[str, Any]:
    value = body.get("input", body)
    if not isinstance(value, dict):
        raise ValueError("Job input must be a JSON object")
    return value


def make_mock_wav(path: Path, seconds: float = 1.2, sample_rate: int = 24000) -> None:
    amplitude = 6000
    frequency = 440
    frames = int(seconds * sample_rate)
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for index in range(frames):
            sample = int(amplitude * math.sin(2 * math.pi * frequency * index / sample_rate))
            wav.writeframesraw(struct.pack("<h", sample))


def make_mock_video(path: Path, seconds: float = 2.0) -> None:
    command = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=size=512x512:rate=24:duration={seconds}",
        "-vf", "format=yuv420p", "-c:v", "libx264", str(path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True)
    except Exception:
        path.with_suffix(".txt").write_text("Mock video generation completed; ffmpeg was unavailable.", encoding="utf-8")
        path.touch()


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
