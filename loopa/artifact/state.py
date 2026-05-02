from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def app_root() -> Path:
    root = os.environ.get("LOOPA_APP_ROOT")
    if not root:
        raise RuntimeError("LOOPA_APP_ROOT is not set; run the artifact under the loopa supervisor.")
    return Path(root)


def runtime_path() -> Path:
    override = os.environ.get("LOOPA_RUNTIME")
    return Path(override) if override else app_root() / "runtime"


def connect() -> sqlite3.Connection:
    """Return a connection to the shared per-app SQLite database."""
    runtime_path().mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(runtime_path() / "state.db")
    conn.row_factory = sqlite3.Row
    return conn
