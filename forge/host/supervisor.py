from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from typing import TextIO

import forge

from . import inbox, registry, status, versions
from .atomic import atomic_write_json
from .config import AppSpec
from .runner import Process
from .status import utc_now


CRASH_WINDOW_SECONDS = 10.0
CRASH_THRESHOLD = 3
TICK_SECONDS = 0.5


class Supervisor:
    def __init__(self, spec: AppSpec) -> None:
        self.spec = spec
        self.process: Process | None = None
        self.artifact_log: TextIO | None = None
        self.processed_task_ids: set[str] = set()
        self.shutting_down = False
        self.recent_crash_times: list[float] = []

    def run(self) -> int:
        self.spec.paths.ensure()
        self.spec.paths.tasks.touch(exist_ok=True)
        if not self.spec.paths.registry.exists():
            registry.write_current(self.spec.paths.registry, self.spec.seed_version)
        self.processed_task_ids = inbox.existing_task_ids(self.spec.paths.tasks)

        self.spec.runner.preflight()

        current = self._current_version()
        self._set_status("ready", current, f"ready: {current}")
        self._launch(current)
        self._log(f"supervisor started for {self.spec.name} with {current}")

        signal.signal(signal.SIGINT, self._signal_shutdown)
        signal.signal(signal.SIGTERM, self._signal_shutdown)

        try:
            while not self.shutting_down:
                self._relaunch_if_needed()
                self._process_pending_tasks()
                time.sleep(TICK_SECONDS)
        finally:
            self._stop()
            self._log("supervisor stopped")
        return 0

    def _signal_shutdown(self, _signum: int, _frame: object) -> None:
        self.shutting_down = True

    def _current_version(self) -> str:
        return registry.read_current(self.spec.paths.registry)

    def _launch(self, version: str) -> None:
        version_dir = self.spec.paths.version_dir(version)
        entry = version_dir / self.spec.entry
        if not entry.exists():
            raise RuntimeError(f"Missing artifact entry point: {entry}")

        if self.artifact_log is None or self.artifact_log.closed:
            self.spec.paths.logs_dir.mkdir(parents=True, exist_ok=True)
            self.artifact_log = self.spec.paths.artifact_log.open("a", encoding="utf-8")

        env = self._build_env()
        self.process = self.spec.runner.launch(entry, env, self.artifact_log)
        self._log(f"launched {version} pid={self.process.pid}")

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["FORGE_APP_ROOT"] = str(self.spec.paths.root)
        env["FORGE_RUNTIME"] = str(self.spec.paths.runtime_dir)
        env["FORGE_ARTIFACT_LOG"] = str(self.spec.paths.artifact_log)
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        forge_parent = str(Path(forge.__file__).resolve().parent.parent)
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            forge_parent if not existing else f"{forge_parent}{os.pathsep}{existing}"
        )
        return env

    def _stop(self) -> None:
        if self.process is not None:
            try:
                self._log(f"stopping artifact pid={self.process.pid}")
                self.spec.runner.stop(self.process)
            except Exception as exc:
                self._log(f"error stopping artifact: {exc}")
            self.process = None
        self._close_log()

    def _close_log(self) -> None:
        if self.artifact_log is not None:
            try:
                self.artifact_log.close()
            except Exception:
                pass
            self.artifact_log = None

    def _relaunch_if_needed(self) -> None:
        if self.process is None:
            return
        return_code = self.process.poll()
        if return_code is None:
            return

        version = self._current_version()
        if return_code == 0:
            self._log(f"artifact {version} closed cleanly")
            self.process = None
            self._close_log()
            self._set_status("closed", version, f"closed: {version}")
            self.shutting_down = True
            return

        self._log(f"artifact {version} exited with code {return_code}")
        self.process = None
        self._close_log()

        now = time.monotonic()
        self.recent_crash_times = [
            t for t in self.recent_crash_times if now - t < CRASH_WINDOW_SECONDS
        ]
        self.recent_crash_times.append(now)
        if len(self.recent_crash_times) >= CRASH_THRESHOLD:
            self._set_status("failed", version, f"failed: {version} crashed repeatedly")
            self.shutting_down = True
            return

        self._set_status("failed", version, f"{version} exited; relaunching")
        try:
            self._launch(version)
        except Exception as exc:
            self._set_status("failed", version, f"failed to relaunch {version}: {exc}")
            self.shutting_down = True
            return
        self._set_status("ready", version, f"ready: {version}")

    def _process_pending_tasks(self) -> None:
        for task in inbox.iter_tasks(self.spec.paths.tasks):
            if task.id in self.processed_task_ids:
                continue
            self.processed_task_ids.add(task.id)
            self._handle_task(task.task)
            return

    def _handle_task(self, task: str) -> None:
        previous_version = self._current_version()
        previous_dir = self.spec.paths.version_dir(previous_version)
        self._log(f"task for {previous_version}: {task}")

        previous_error: str | None = None
        last_error: str | None = None
        attempts_used = 0

        for attempt in range(1, self.spec.max_attempts + 1):
            attempts_used = attempt
            label = f"attempt {attempt}/{self.spec.max_attempts}"
            self._set_status(
                "implementing", previous_version, f"implementing ({label}): {task}"
            )

            target_dir = versions.allocate_next(self.spec.paths.versions_dir)
            new_version = target_dir.name

            try:
                self.spec.implementor.generate(
                    previous_dir, task, target_dir, previous_error
                )
                self._write_manifest(target_dir, new_version, previous_version, task)
                for validator in self.spec.validators:
                    validator.validate(target_dir)
            except Exception as exc:
                last_error = str(exc)
                previous_error = last_error
                self._log(f"implementor/validator failed ({label}): {last_error}")
                if "Ollama is unavailable" in last_error:
                    break
                continue

            launch_error = self._swap(previous_version, new_version)
            if launch_error is None:
                return
            last_error = launch_error
            previous_error = launch_error

        self._set_status(
            "failed",
            self._current_version(),
            f"failed after {attempts_used} attempt(s): {last_error or 'unknown error'}",
        )

    def _swap(self, previous_version: str, new_version: str) -> str | None:
        try:
            self._stop()
            registry.write_current(self.spec.paths.registry, new_version)
            self._launch(new_version)
        except Exception as exc:
            reason = f"{new_version} failed to launch: {exc}"
            self._rollback(previous_version, reason)
            return reason

        if self.process is None:
            reason = f"{new_version} process missing after launch"
            self._rollback(previous_version, reason)
            return reason

        result = self.spec.probe.check(self.process)
        if not result.ok:
            reason = result.reason or "probe failed"
            self._rollback(previous_version, reason)
            return reason

        self._set_status("ready", new_version, f"ready: {new_version}")
        self._log(f"ready: {new_version}")
        return None

    def _rollback(self, previous_version: str, reason: str) -> None:
        self._log(f"rolling back to {previous_version}: {reason}")
        self._stop()
        registry.write_current(self.spec.paths.registry, previous_version)
        try:
            self._launch(previous_version)
        except Exception as exc:
            self._set_status(
                "failed",
                previous_version,
                f"rollback to {previous_version} failed: {exc}",
            )
            self.shutting_down = True
            return
        self._set_status("rolled_back", previous_version, f"rolled back: {reason}")

    def _write_manifest(
        self, version_dir: Path, version: str, parent: str, task: str
    ) -> None:
        atomic_write_json(
            version_dir / "manifest.json",
            {
                "version": version,
                "parent": parent,
                "created_at": utc_now(),
                "task": task,
                "entry": self.spec.entry,
            },
        )

    def _set_status(self, state: str, version: str, message: str) -> None:
        status.write_status(self.spec.paths.status, state, version, message)

    def _log(self, message: str) -> None:
        self.spec.paths.logs_dir.mkdir(parents=True, exist_ok=True)
        with self.spec.paths.supervisor_log.open("a", encoding="utf-8") as f:
            f.write(f"{utc_now()} {message}\n")
