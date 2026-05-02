from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .atomic import atomic_write_json


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_status(status_path: Path, state: str, version: str, message: str) -> None:
    atomic_write_json(
        status_path,
        {
            "state": state,
            "version": version,
            "message": message,
            "updated_at": utc_now(),
        },
    )
