from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass
class Task:
    id: str
    task: str


def iter_tasks(tasks_path: Path) -> Iterator[Task]:
    try:
        text = tasks_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return

    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        task_id = payload.get("id")
        task_text = payload.get("task")
        if isinstance(task_id, str) and isinstance(task_text, str):
            yield Task(id=task_id, task=task_text)


def existing_task_ids(tasks_path: Path) -> set[str]:
    return {task.id for task in iter_tasks(tasks_path)}
