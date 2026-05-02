from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class ValidationError(RuntimeError):
    pass


class Validator(Protocol):
    def validate(self, artifact_dir: Path) -> None: ...


@dataclass
class CompilePythonValidator:
    """Compiles the entry file in a subprocess; raises on syntax errors."""

    entry: str = "main.py"
    interpreter: str | None = None
    timeout_seconds: float = 30.0

    def validate(self, artifact_dir: Path) -> None:
        target = artifact_dir / self.entry
        if not target.exists():
            raise ValidationError(f"Generated artifact is missing {self.entry}.")

        command = (
            "import pathlib, sys; "
            "path = pathlib.Path(sys.argv[1]); "
            "compile(path.read_text(encoding='utf-8'), str(path), 'exec')"
        )
        result = subprocess.run(
            [self.interpreter or sys.executable, "-B", "-c", command, str(target)],
            cwd=artifact_dir,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        if result.returncode != 0:
            details = (result.stderr or result.stdout).strip()
            raise ValidationError(details or f"compile failed for {target}")


@dataclass
class TokenPolicyValidator:
    """Substring blocklist + requirelist on the entry file."""

    forbidden: list[str] = field(default_factory=list)
    required: list[str] = field(default_factory=list)
    entry: str = "main.py"

    def validate(self, artifact_dir: Path) -> None:
        target = artifact_dir / self.entry
        if not target.exists():
            raise ValidationError(f"Generated artifact is missing {self.entry}.")
        source = target.read_text(encoding="utf-8")

        for needle in self.forbidden:
            if needle in source:
                raise ValidationError(f"Forbidden token in generated source: {needle!r}")

        missing = [needle for needle in self.required if needle not in source]
        if missing:
            quoted = ", ".join(repr(needle) for needle in missing)
            raise ValidationError(f"Generated source missing required token(s): {quoted}")
