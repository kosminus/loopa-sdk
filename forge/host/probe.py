from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from .runner import Process


@dataclass
class ProbeResult:
    ok: bool
    reason: str | None = None


class Probe(Protocol):
    def check(self, process: Process) -> ProbeResult: ...


@dataclass
class ProcessAliveProbe:
    """Process must stay alive for `window_seconds`."""

    window_seconds: float = 10.0
    poll_interval: float = 0.25

    def check(self, process: Process) -> ProbeResult:
        deadline = time.monotonic() + self.window_seconds
        while time.monotonic() < deadline:
            return_code = process.poll()
            if return_code is not None:
                return ProbeResult(
                    ok=False,
                    reason=f"process exited during startup with code {return_code}",
                )
            time.sleep(self.poll_interval)
        return ProbeResult(ok=True)
