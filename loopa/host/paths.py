from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    root: Path
    versions_dir: Path
    runtime_dir: Path
    logs_dir: Path

    @classmethod
    def from_root(cls, root: Path) -> "AppPaths":
        return cls(
            root=root,
            versions_dir=root / "versions",
            runtime_dir=root / "runtime",
            logs_dir=root / "logs",
        )

    @property
    def registry(self) -> Path:
        return self.runtime_dir / "registry.json"

    @property
    def status(self) -> Path:
        return self.runtime_dir / "status.json"

    @property
    def tasks(self) -> Path:
        return self.runtime_dir / "tasks.jsonl"

    @property
    def supervisor_log(self) -> Path:
        return self.logs_dir / "supervisor.log"

    @property
    def artifact_log(self) -> Path:
        return self.logs_dir / "artifact.log"

    def version_dir(self, version: str) -> Path:
        return self.versions_dir / version

    def ensure(self) -> None:
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
