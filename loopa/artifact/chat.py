from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def app_root() -> Path:
    root = os.environ.get("LOOPA_APP_ROOT")
    if not root:
        raise RuntimeError("LOOPA_APP_ROOT is not set; run the artifact under the loopa supervisor.")
    return Path(root)


def runtime_path() -> Path:
    override = os.environ.get("LOOPA_RUNTIME")
    return Path(override) if override else app_root() / "runtime"


def status_path() -> Path:
    return runtime_path() / "status.json"


def tasks_path() -> Path:
    return runtime_path() / "tasks.jsonl"


def read_status() -> dict:
    try:
        return json.loads(status_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"state": "unknown", "message": "status unavailable"}
    except json.JSONDecodeError:
        return {"state": "unknown", "message": "status unreadable"}


def send_task(task: str) -> str:
    """Append a user task to runtime/tasks.jsonl and return its id."""
    cleaned = task.strip()
    if not cleaned:
        raise ValueError("Task cannot be empty.")

    runtime_path().mkdir(parents=True, exist_ok=True)
    task_id = f"{datetime.now(timezone.utc).isoformat()}-{uuid4().hex[:8]}"
    payload = {"id": task_id, "task": cleaned}

    with tasks_path().open("a", encoding="utf-8") as task_file:
        task_file.write(json.dumps(payload, ensure_ascii=True) + "\n")

    return task_id
