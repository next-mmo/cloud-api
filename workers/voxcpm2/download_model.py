from __future__ import annotations

import os
from pathlib import Path

from huggingface_hub import snapshot_download


def main() -> None:
    repo_id = os.getenv("MODEL_ID", "openbmb/VoxCPM2")
    revision = os.getenv("MODEL_REVISION", "main")
    target = Path(os.getenv("MODEL_DIR", "/models/VoxCPM2"))
    max_workers = int(os.getenv("HF_DOWNLOAD_MAX_WORKERS", "4"))
    token = os.getenv("HF_TOKEN") or None

    target.mkdir(parents=True, exist_ok=True)
    print(
        f"Downloading {repo_id}@{revision} to {target} "
        f"with max_workers={max_workers}",
        flush=True,
    )

    resolved_path = snapshot_download(
        repo_id=repo_id,
        revision=revision,
        local_dir=str(target),
        max_workers=max_workers,
        token=token,
    )

    weight_files = list(target.rglob("*.safetensors"))
    total_weight_bytes = sum(path.stat().st_size for path in weight_files)
    if not weight_files or total_weight_bytes < 1_000_000_000:
        raise RuntimeError(
            "VoxCPM2 download is incomplete: expected at least 1 GB of "
            f"safetensors weights, found {total_weight_bytes} bytes"
        )

    print(
        f"Model snapshot ready at {resolved_path}; "
        f"validated {len(weight_files)} safetensors file(s), "
        f"{total_weight_bytes / 1_000_000_000:.2f} GB total",
        flush=True,
    )


if __name__ == "__main__":
    main()
