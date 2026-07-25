from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from .db import VaultRecord
from .settings_catalog import allowed_keys, secret_keys

VAULT_ROW_ID = "default"
ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")


class VaultError(RuntimeError):
    pass


def _fernet() -> Fernet:
    raw = (os.getenv("SETTINGS_ENCRYPTION_KEY") or "").strip()
    if not raw:
        raise VaultError(
            "SETTINGS_ENCRYPTION_KEY is required to store encrypted settings. "
            "Add it to the controller host .env (any long random string works)."
        )
    # Accept a Fernet key, or derive one from an arbitrary passphrase.
    try:
        return Fernet(raw.encode("utf-8"))
    except Exception:
        digest = hashlib.sha256(raw.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_mapping(values: dict[str, str]) -> str:
    payload = json.dumps(values, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _fernet().encrypt(payload).decode("utf-8")


def decrypt_mapping(ciphertext: str) -> dict[str, str]:
    try:
        raw = _fernet().decrypt(ciphertext.encode("utf-8"))
    except InvalidToken as exc:
        raise VaultError("Unable to decrypt settings vault (wrong SETTINGS_ENCRYPTION_KEY?)") from exc
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise VaultError("Corrupt settings vault")
    return {str(k): str(v) for k, v in data.items() if v is not None}


def parse_env_text(text: str) -> dict[str, str]:
    allowed = allowed_keys()
    out: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = ENV_LINE.match(line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if key not in allowed:
            continue
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        out[key] = value
    return out


def load_vault(db: Session) -> dict[str, str]:
    row = db.get(VaultRecord, VAULT_ROW_ID)
    if not row or not row.ciphertext:
        return {}
    return decrypt_mapping(row.ciphertext)


def save_vault(db: Session, values: dict[str, str]) -> dict[str, str]:
    allowed = allowed_keys()
    cleaned = {k: v for k, v in values.items() if k in allowed and v is not None}
    # Drop empty strings so cleared fields disappear.
    cleaned = {k: v for k, v in cleaned.items() if str(v).strip() != ""}
    row = db.get(VaultRecord, VAULT_ROW_ID)
    if not cleaned:
        if row:
            db.delete(row)
            db.commit()
        apply_vault_to_environ({})
        return {}
    ciphertext = encrypt_mapping(cleaned)
    if row is None:
        row = VaultRecord(id=VAULT_ROW_ID, ciphertext=ciphertext)
        db.add(row)
    else:
        row.ciphertext = ciphertext
    db.commit()
    apply_vault_to_environ(cleaned)
    return cleaned


def merge_updates(current: dict[str, str], updates: dict[str, str | None]) -> dict[str, str]:
    """Merge UI updates. None or '__CLEAR__' removes a key. Empty string keeps existing."""
    next_values = dict(current)
    for key, value in updates.items():
        if key not in allowed_keys():
            continue
        if value is None or value == "__CLEAR__":
            next_values.pop(key, None)
            continue
        if value == "":
            continue
        next_values[key] = value
    return next_values


def mask_value(key: str, value: str) -> dict[str, Any]:
    if key in secret_keys():
        hint = value[-4:] if len(value) >= 4 else ""
        return {
            "key": key,
            "configured": True,
            "secret": True,
            "hint": f"••••{hint}" if hint else "••••",
            "value": None,
        }
    return {
        "key": key,
        "configured": True,
        "secret": False,
        "hint": None,
        "value": value,
    }


def public_status(values: dict[str, str]) -> dict[str, Any]:
    fields = []
    for key in sorted(allowed_keys()):
        if key in values and str(values[key]).strip() != "":
            fields.append(mask_value(key, values[key]))
        else:
            fields.append(
                {
                    "key": key,
                    "configured": False,
                    "secret": key in secret_keys(),
                    "hint": None,
                    "value": None,
                }
            )
    return {"configured_count": sum(1 for item in fields if item["configured"]), "fields": fields}


_host_snapshot: dict[str, str | None] | None = None
_applied_keys: set[str] = set()


def apply_vault_to_environ(values: dict[str, str]) -> None:
    """Push vault values into process env; restore host values when a vault key is removed."""
    global _host_snapshot, _applied_keys
    allowed = allowed_keys()
    if _host_snapshot is None:
        _host_snapshot = {key: os.environ.get(key) for key in allowed}
    for key in list(_applied_keys):
        if key not in values:
            original = _host_snapshot.get(key)
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original
    for key, value in values.items():
        if key in allowed:
            os.environ[key] = value
    _applied_keys = set(values.keys()) & allowed
