from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Protocol, TextIO


class Process(Protocol):
    pid: int

    def poll(self) -> int | None: ...
    def wait(self, timeout: float | None = None) -> int: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...


class Runner(Protocol):
    def preflight(self) -> None: ...
    def launch(
        self,
        entry: Path,
        env: Mapping[str, str],
        log: TextIO,
    ) -> Process: ...
    def stop(self, process: Process, timeout: float = 5.0) -> None: ...


@dataclass
class PythonRunner:
    """Launches `<python> <entry>` from the artifact directory."""

    interpreter: str | None = None
    require_tk: bool = False
    _resolved: str | None = field(default=None, init=False, repr=False)

    def preflight(self) -> None:
        self._resolved = self._find_interpreter()

    def launch(
        self,
        entry: Path,
        env: Mapping[str, str],
        log: TextIO,
    ) -> subprocess.Popen:
        interpreter = self._resolved or self._find_interpreter()
        return subprocess.Popen(
            [interpreter, str(entry)],
            cwd=entry.parent,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=dict(env),
        )

    def stop(self, process: subprocess.Popen, timeout: float = 5.0) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=timeout)

    def _find_interpreter(self) -> str:
        candidates: list[str | None] = [
            self.interpreter,
            os.environ.get("LOOPA_PYTHON"),
            sys.executable,
            shutil.which("python3"),
            shutil.which("python"),
        ]
        seen: set[str] = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            if not self.require_tk or self._has_tk(candidate):
                return candidate

        suffix = " with tkinter support" if self.require_tk else ""
        raise RuntimeError(f"No suitable Python interpreter found{suffix}.")

    @staticmethod
    def _has_tk(executable: str) -> bool:
        try:
            result = subprocess.run(
                [executable, "-c", "import tkinter"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0
