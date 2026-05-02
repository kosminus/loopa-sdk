from __future__ import annotations

import json
from pathlib import Path

from .atomic import atomic_write_json


DEFAULT_VERSION = "v0"


def read_current(registry_path: Path) -> str:
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_VERSION

    version = registry.get("current_version", DEFAULT_VERSION)
    if not isinstance(version, str):
        return DEFAULT_VERSION
    return version


def write_current(registry_path: Path, version: str) -> None:
    atomic_write_json(registry_path, {"current_version": version})
