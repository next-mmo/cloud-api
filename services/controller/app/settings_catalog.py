from __future__ import annotations

from typing import Any, Literal

FieldKind = Literal["secret", "text", "url", "number"]


def _field(
    key: str,
    label: str,
    *,
    kind: FieldKind = "text",
    help: str = "",
    placeholder: str = "",
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "kind": kind,
        "help": help,
        "placeholder": placeholder,
        "secret": kind == "secret",
    }


SETTINGS_GROUPS: list[dict[str, Any]] = [
    {
        "id": "workers",
        "title": "Workers",
        "description": "Direct FastAPI GPU worker URLs used by Local / Custom compute.",
        "docs_url": None,
        "fields": [
            _field("VOX_WORKER_URL", "VoxCPM2 worker URL", kind="url", placeholder="http://host:8011"),
            _field("WAN_WORKER_URL", "WanGP worker URL", kind="url", placeholder="http://host:8012"),
            _field("CUSTOM_WORKER_URL", "Custom worker URL", kind="url", placeholder="https://worker.example.com"),
            _field("CUSTOM_WORKER_TOKEN", "Custom worker token", kind="secret"),
        ],
    },
    {
        "id": "salad",
        "title": "SaladCloud",
        "description": "Job Queue API credentials and queue names.",
        "docs_url": "https://docs.salad.com/",
        "console_url": "https://portal.salad.com/",
        "fields": [
            _field("SALAD_API_KEY", "API key", kind="secret", help="From Salad portal → API Access"),
            _field("SALAD_ORGANIZATION", "Organization"),
            _field("SALAD_PROJECT", "Project"),
            _field("SALAD_VOX_QUEUE", "VoxCPM2 queue", placeholder="voxcpm2-jobs"),
            _field("SALAD_WAN_QUEUE", "WanGP queue", placeholder="wangp-jobs"),
            _field("SALAD_WEBHOOK_BASE_URL", "Webhook base URL", kind="url", placeholder="https://your-controller.example"),
            _field("SALAD_WEBHOOK_SECRET", "Webhook secret", kind="secret"),
        ],
    },
    {
        "id": "runpod",
        "title": "RunPod",
        "description": "Serverless endpoint IDs for TTS and video workers.",
        "docs_url": "https://docs.runpod.io/serverless/overview",
        "console_url": "https://www.runpod.io/console/user/settings",
        "fields": [
            _field("RUNPOD_API_KEY", "API key", kind="secret", help="RunPod console → Settings → API Keys"),
            _field("RUNPOD_VOX_ENDPOINT_ID", "VoxCPM2 endpoint ID"),
            _field("RUNPOD_WAN_ENDPOINT_ID", "WanGP endpoint ID"),
        ],
    },
    {
        "id": "clore",
        "title": "Clore.ai",
        "description": "Marketplace rental credentials. After deploy, set Custom worker URL to the instance URL.",
        "docs_url": "https://docs.clore.ai/",
        "console_url": "https://clore.ai/",
        "fields": [
            _field("CLORE_API_KEY", "API key", kind="secret"),
            _field("CLORE_SERVER_ID", "Preferred server ID"),
            _field("CLORE_WORKER_URL", "Worker URL", kind="url"),
            _field("CLORE_MAX_USD_PER_HOUR", "Max USD / hour", kind="number"),
            _field("CLORE_MIN_RAM_GB", "Min RAM (GB)", kind="number", placeholder="24"),
        ],
    },
    {
        "id": "vast",
        "title": "Vast.ai",
        "description": "Rent a remote GPU. Having VoxCPM2 on your laptop does not use Vast’s GPU — inference runs on the instance. Fast path: create (or reuse) an instance with the prebuilt worker image, then paste VAST_WORKER_URL. No need to install VoxCPM2 on your PC for Vast jobs.",
        "docs_url": "https://vast.ai/docs/",
        "console_url": "https://cloud.vast.ai/",
        "keys_url": "https://cloud.vast.ai/manage-keys/",
        "fields": [
            _field("VAST_API_KEY", "API key", kind="secret", help="https://cloud.vast.ai/manage-keys/"),
            _field(
                "VAST_WORKER_URL",
                "Worker URL",
                kind="url",
                help="HTTP URL of a running Vast instance worker. Reuse an existing instance to skip create.",
            ),
            _field("VAST_INSTANCE_ID", "Instance ID"),
            _field("VAST_OFFER_ID", "Offer ID"),
            _field("VAST_GPU_NAME", "GPU name", placeholder="RTX 4090"),
            _field("VAST_MAX_USD_PER_HOUR", "Max USD / hour", kind="number"),
            _field("VAST_MIN_RAM_GB", "Min RAM (GB)", kind="number", placeholder="24"),
            _field("VAST_NUM_GPUS", "GPU count", kind="number", placeholder="1"),
            _field(
                "VAST_IMAGE_LOGIN",
                "Private registry login",
                kind="secret",
                help='Example: -u USER -p ghp_xxx ghcr.io',
            ),
            _field("VOXCPM2_IMAGE", "VoxCPM2 image", placeholder="ghcr.io/org/cloud-api-voxcpm2:latest"),
        ],
    },
    {
        "id": "r2",
        "title": "Cloudflare R2 / S3",
        "description": "S3-compatible object storage for uploads and outputs.",
        "docs_url": "https://developers.cloudflare.com/r2/",
        "console_url": "https://dash.cloudflare.com/",
        "fields": [
            _field("S3_ENDPOINT_URL", "Endpoint URL", kind="url"),
            _field("S3_REGION", "Region", placeholder="auto"),
            _field("S3_ACCESS_KEY_ID", "Access key ID", kind="secret"),
            _field("S3_SECRET_ACCESS_KEY", "Secret access key", kind="secret"),
            _field("S3_BUCKET", "Bucket"),
            _field("S3_PUBLIC_BASE_URL", "Public base URL", kind="url"),
        ],
    },
    {
        "id": "google_drive",
        "title": "Google Drive",
        "description": "Easiest: use Connect with Google (rclone built-in app — no Cloud Console). Advanced: paste your own OAuth client + refresh token.",
        "docs_url": "https://rclone.org/drive/",
        "console_url": "https://drive.google.com/",
        "keys_url": "https://myaccount.google.com/permissions",
        "fields": [
            _field(
                "GOOGLE_DRIVE_CLIENT_ID",
                "OAuth client ID (optional)",
                kind="secret",
                help="Leave blank to use rclone's built-in Google app.",
            ),
            _field(
                "GOOGLE_DRIVE_CLIENT_SECRET",
                "OAuth client secret (optional)",
                kind="secret",
                help="Leave blank with the easy Connect button.",
            ),
            _field(
                "GOOGLE_DRIVE_REFRESH_TOKEN",
                "Refresh token",
                kind="secret",
                help="Filled automatically by Connect with Google.",
            ),
            _field("GOOGLE_DRIVE_FOLDER_ID", "Folder ID", help="Optional destination folder ID"),
            _field("GOOGLE_DRIVE_MAKE_PUBLIC", "Make files public", placeholder="false"),
        ],
    },
]


def allowed_keys() -> set[str]:
    return {field["key"] for group in SETTINGS_GROUPS for field in group["fields"]}


def secret_keys() -> set[str]:
    return {field["key"] for group in SETTINGS_GROUPS for field in group["fields"] if field["secret"]}


def schema_payload() -> dict[str, Any]:
    return {"groups": SETTINGS_GROUPS}
