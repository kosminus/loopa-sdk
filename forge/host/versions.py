from __future__ import annotations

import re
from pathlib import Path


VERSION_PATTERN = re.compile(r"v(\d+)")


def allocate_next(versions_dir: Path) -> Path:
    versions_dir.mkdir(parents=True, exist_ok=True)
    existing: list[int] = []
    for path in versions_dir.iterdir():
        if not path.is_dir():
            continue
        match = VERSION_PATTERN.fullmatch(path.name)
        if match:
            existing.append(int(match.group(1)))

    next_number = max(existing, default=-1) + 1
    while True:
        target = versions_dir / f"v{next_number}"
        if not target.exists():
            target.mkdir(parents=True)
            return target
        next_number += 1
