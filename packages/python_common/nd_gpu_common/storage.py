from __future__ import annotations

import io
import mimetypes
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse


@dataclass(slots=True)
class StoredObject:
    uri: str
    public_url: str | None = None
    provider: str = "local"


class Storage(Protocol):
    def upload(self, local_path: Path, object_name: str | None = None) -> StoredObject: ...
    def download(self, uri: str, destination: Path) -> Path: ...


def _safe_name(name: str) -> str:
    clean = "".join(ch for ch in name if ch.isalnum() or ch in "._-/")
    return clean.strip("/") or f"file-{uuid.uuid4().hex}"


class LocalStorage:
    def __init__(self) -> None:
        self.root = Path(os.getenv("LOCAL_STORAGE_DIR", "./data/files")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.public_base = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

    def upload(self, local_path: Path, object_name: str | None = None) -> StoredObject:
        name = _safe_name(object_name or f"outputs/{uuid.uuid4().hex}-{local_path.name}")
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, target)
        return StoredObject(
            uri=f"local://{name}",
            public_url=f"{self.public_base}/files/{name}",
            provider="local",
        )

    def download(self, uri: str, destination: Path) -> Path:
        if uri.startswith("local://"):
            source = self.root / uri.removeprefix("local://")
        elif uri.startswith("file://"):
            source = Path(urlparse(uri).path)
        else:
            source = Path(uri)
        if not source.exists():
            raise FileNotFoundError(f"Local object not found: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination


class S3Storage:
    def __init__(self) -> None:
        import boto3

        self.bucket = os.environ["S3_BUCKET"]
        self.public_base = os.getenv("S3_PUBLIC_BASE_URL", "").rstrip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
            region_name=os.getenv("S3_REGION", "auto"),
            aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
        )

    def upload(self, local_path: Path, object_name: str | None = None) -> StoredObject:
        key = _safe_name(object_name or f"outputs/{uuid.uuid4().hex}-{local_path.name}")
        content_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
        self.client.upload_file(str(local_path), self.bucket, key, ExtraArgs={"ContentType": content_type})
        public_url = f"{self.public_base}/{key}" if self.public_base else None
        return StoredObject(uri=f"s3://{self.bucket}/{key}", public_url=public_url, provider="r2")

    def download(self, uri: str, destination: Path) -> Path:
        parsed = urlparse(uri)
        if parsed.scheme not in {"s3", "r2"}:
            raise ValueError(f"Expected s3:// or r2:// URI, got {uri}")
        bucket = parsed.netloc or self.bucket
        key = parsed.path.lstrip("/")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(bucket, key, str(destination))
        return destination


class GoogleDriveStorage:
    def __init__(self) -> None:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        credentials = Credentials(
            token=None,
            refresh_token=os.environ["GOOGLE_DRIVE_REFRESH_TOKEN"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["GOOGLE_DRIVE_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_DRIVE_CLIENT_SECRET"],
            scopes=["https://www.googleapis.com/auth/drive.file"],
        )
        self.service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self.folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID") or None
        self.make_public = os.getenv("GOOGLE_DRIVE_MAKE_PUBLIC", "false").lower() == "true"

    def upload(self, local_path: Path, object_name: str | None = None) -> StoredObject:
        from googleapiclient.http import MediaFileUpload

        name = Path(object_name or local_path.name).name
        metadata: dict[str, object] = {"name": name}
        if self.folder_id:
            metadata["parents"] = [self.folder_id]
        media = MediaFileUpload(
            str(local_path),
            mimetype=mimetypes.guess_type(local_path.name)[0] or "application/octet-stream",
            resumable=True,
        )
        created = self.service.files().create(
            body=metadata,
            media_body=media,
            fields="id,webViewLink,webContentLink",
        ).execute()
        file_id = created["id"]
        if self.make_public:
            self.service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
            ).execute()
        info = self.service.files().get(
            fileId=file_id,
            fields="id,webViewLink,webContentLink",
        ).execute()
        return StoredObject(
            uri=f"gdrive://{file_id}",
            public_url=info.get("webContentLink") or info.get("webViewLink"),
            provider="google_drive",
        )

    def download(self, uri: str, destination: Path) -> Path:
        from googleapiclient.http import MediaIoBaseDownload

        file_id = uri.removeprefix("gdrive://")
        request = self.service.files().get_media(fileId=file_id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as handle:
            downloader = MediaIoBaseDownload(handle, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return destination


class StorageFactory:
    @staticmethod
    def create(provider: str | None = None) -> Storage:
        selected = (provider or os.getenv("STORAGE_PROVIDER", "local")).lower()
        if selected in {"r2", "s3", "s3_compatible"}:
            return S3Storage()
        if selected in {"google_drive", "gdrive", "drive"}:
            return GoogleDriveStorage()
        return LocalStorage()
