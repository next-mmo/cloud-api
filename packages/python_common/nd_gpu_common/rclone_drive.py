"""Rclone shared Google Drive OAuth app helpers (easy connect, no Cloud Console).

Uses the same public client credentials rclone ships for Google Drive when
client_id / client_secret are left blank. See https://rclone.org/drive/
"""

from __future__ import annotations

import os

# Public rclone Drive OAuth client (rclone backend/drive/drive.go).
RCLONE_DRIVE_CLIENT_ID = "202264815644.apps.googleusercontent.com"
# Revealed from rclone's obscured default (not a private secret — shipped in rclone).
RCLONE_DRIVE_CLIENT_SECRET = "X4Z3ca8xfWDb1Voo-F9a7ZxJ"
RCLONE_REDIRECT_URI = "http://127.0.0.1:53682/"
RCLONE_CALLBACK_HOST = "127.0.0.1"
RCLONE_CALLBACK_PORT = 53682
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"


def resolve_drive_oauth_client() -> tuple[str, str]:
    """Return (client_id, client_secret), falling back to rclone defaults."""
    client_id = (os.getenv("GOOGLE_DRIVE_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("GOOGLE_DRIVE_CLIENT_SECRET") or "").strip()
    if client_id and client_secret:
        return client_id, client_secret
    return RCLONE_DRIVE_CLIENT_ID, RCLONE_DRIVE_CLIENT_SECRET
