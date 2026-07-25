from __future__ import annotations

import secrets
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import httpx
from sqlalchemy.orm import Session

from nd_gpu_common.rclone_drive import (
    DRIVE_FILE_SCOPE,
    RCLONE_CALLBACK_HOST,
    RCLONE_CALLBACK_PORT,
    RCLONE_DRIVE_CLIENT_ID,
    RCLONE_DRIVE_CLIENT_SECRET,
    RCLONE_REDIRECT_URI,
)

from .secret_vault import VaultError, load_vault, merge_updates, public_status, save_vault

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


@dataclass
class OAuthSession:
    state: str
    status: str = "pending"  # pending | succeeded | failed | expired
    auth_url: str = ""
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    server: HTTPServer | None = None
    thread: threading.Thread | None = None


_lock = threading.Lock()
_session: OAuthSession | None = None


def get_oauth_status() -> dict[str, Any]:
    with _lock:
        if _session is None:
            return {"status": "idle", "auth_url": None, "error": None}
        if _session.status == "pending" and time.time() - _session.started_at > 180:
            _stop_server_locked(_session)
            _session.status = "expired"
            _session.error = "Sign-in timed out. Click Connect again."
        return {
            "status": _session.status,
            "auth_url": _session.auth_url,
            "error": _session.error,
            "mode": "rclone_default",
            "hint": "Uses rclone's built-in Google app — no Cloud Console setup.",
        }


def _stop_server_locked(session: OAuthSession) -> None:
    if session.server is not None:
        try:
            session.server.shutdown()
        except Exception:
            pass
        try:
            session.server.server_close()
        except Exception:
            pass
        session.server = None


def start_oauth() -> dict[str, Any]:
    global _session
    with _lock:
        if _session and _session.status == "pending":
            return {
                "status": _session.status,
                "auth_url": _session.auth_url,
                "error": _session.error,
                "mode": "rclone_default",
                "hint": "Finish the browser Allow step, or wait for timeout and try again.",
            }

        state = secrets.token_urlsafe(24)
        params = {
            "client_id": RCLONE_DRIVE_CLIENT_ID,
            "redirect_uri": RCLONE_REDIRECT_URI,
            "response_type": "code",
            "scope": DRIVE_FILE_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
        session = OAuthSession(state=state, auth_url=auth_url)

        result_box: dict[str, Any] = {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                return

            def do_GET(self) -> None:  # noqa: N802
                parsed = urllib.parse.urlparse(self.path)
                query = urllib.parse.parse_qs(parsed.query)
                if parsed.path not in {"/", "/auth", ""}:
                    self.send_response(404)
                    self.end_headers()
                    return
                code = (query.get("code") or [None])[0]
                returned_state = (query.get("state") or [None])[0]
                error = (query.get("error") or [None])[0]
                if error:
                    result_box["error"] = error
                elif not code or returned_state != state:
                    result_box["error"] = "Invalid OAuth callback"
                else:
                    result_box["code"] = code
                body = (
                    "<html><body style='font-family:system-ui;padding:40px'>"
                    "<h2>Google Drive connected</h2>"
                    "<p>You can close this tab and return to the studio Secrets page.</p>"
                    "</body></html>"
                    if "code" in result_box
                    else "<html><body style='font-family:system-ui;padding:40px'>"
                    "<h2>Google sign-in failed</h2>"
                    f"<p>{result_box.get('error', 'Unknown error')}</p></body></html>"
                )
                payload = body.encode("utf-8")
                self.send_response(200 if "code" in result_box else 400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

                def finish() -> None:
                    time.sleep(0.2)
                    try:
                        httpd.shutdown()
                    except Exception:
                        pass

                threading.Thread(target=finish, daemon=True).start()

        try:
            httpd = HTTPServer((RCLONE_CALLBACK_HOST, RCLONE_CALLBACK_PORT), Handler)
        except OSError as exc:
            raise RuntimeError(
                f"Could not bind {RCLONE_CALLBACK_HOST}:{RCLONE_CALLBACK_PORT} for Google OAuth "
                f"(is rclone config or another connect flow already running?): {exc}"
            ) from exc

        session.server = httpd

        def serve() -> None:
            global _session
            try:
                httpd.serve_forever(poll_interval=0.3)
            finally:
                code = result_box.get("code")
                error = result_box.get("error")
                with _lock:
                    current = _session
                    if current is None or current.state != state:
                        return
                    if error and not code:
                        current.status = "failed"
                        current.error = str(error)
                        _stop_server_locked(current)
                        return
                    if not code:
                        if current.status == "pending":
                            current.status = "failed"
                            current.error = current.error or "OAuth callback closed without a code"
                        _stop_server_locked(current)
                        return
                try:
                    refresh_token = _exchange_code(str(code))
                    _persist_refresh_token(refresh_token)
                    with _lock:
                        if _session and _session.state == state:
                            _session.status = "succeeded"
                            _session.error = None
                            _stop_server_locked(_session)
                except Exception as exc:  # noqa: BLE001
                    with _lock:
                        if _session and _session.state == state:
                            _session.status = "failed"
                            _session.error = str(exc)
                            _stop_server_locked(_session)

        thread = threading.Thread(target=serve, daemon=True, name="gdrive-oauth")
        session.thread = thread
        _session = session
        thread.start()
        return {
            "status": "pending",
            "auth_url": auth_url,
            "error": None,
            "mode": "rclone_default",
            "hint": "A browser window will ask you to Allow access. No Google Cloud Console app needed.",
        }


def _exchange_code(code: str) -> str:
    with httpx.Client(timeout=30) as client:
        response = client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": RCLONE_DRIVE_CLIENT_ID,
                "client_secret": RCLONE_DRIVE_CLIENT_SECRET,
                "redirect_uri": RCLONE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
    if response.is_error:
        raise RuntimeError(f"Google token exchange failed: {response.status_code} {response.text[:400]}")
    data = response.json()
    refresh = data.get("refresh_token")
    if not refresh:
        raise RuntimeError(
            "Google did not return a refresh_token. Revoke prior access for rclone/this app in "
            "https://myaccount.google.com/permissions and try Connect again."
        )
    return str(refresh)


def _persist_refresh_token(refresh_token: str) -> None:
    from .db import SessionLocal

    db: Session = SessionLocal()
    try:
        try:
            current = load_vault(db)
        except VaultError:
            current = {}
        merged = merge_updates(
            current,
            {
                # Prefer rclone defaults at runtime; clear custom client so easy mode stays active.
                "GOOGLE_DRIVE_CLIENT_ID": "__CLEAR__",
                "GOOGLE_DRIVE_CLIENT_SECRET": "__CLEAR__",
                "GOOGLE_DRIVE_REFRESH_TOKEN": refresh_token,
            },
        )
        save_vault(db, merged)
    finally:
        db.close()


def oauth_public_settings(db: Session) -> dict[str, Any]:
    try:
        values = load_vault(db)
    except VaultError as exc:
        raise RuntimeError(str(exc)) from exc
    status = public_status(values)
    status["oauth"] = get_oauth_status()
    status["google_drive_connected"] = bool(values.get("GOOGLE_DRIVE_REFRESH_TOKEN"))
    return status
