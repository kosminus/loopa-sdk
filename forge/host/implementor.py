from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class ImplementorError(RuntimeError):
    pass


class Implementor(Protocol):
    def generate(
        self,
        current_dir: Path,
        task: str,
        target_dir: Path,
        previous_error: str | None,
    ) -> None: ...


@dataclass
class OllamaImplementor:
    """Asks a local Ollama model for the next entry file."""

    model: str
    prompt_path: Path
    entry: str = "main.py"
    url: str = "http://localhost:11434/api/generate"
    timeout_seconds: float = 300.0
    extra_context_files: tuple[Path, ...] = field(default_factory=tuple)

    def generate(
        self,
        current_dir: Path,
        task: str,
        target_dir: Path,
        previous_error: str | None,
    ) -> None:
        source = (current_dir / self.entry).read_text(encoding="utf-8")
        system_prompt = self.prompt_path.read_text(encoding="utf-8")

        sections = [
            f"CURRENT {self.entry}:\n```python\n{source}\n```",
        ]
        for context_path in self.extra_context_files:
            content = context_path.read_text(encoding="utf-8")
            sections.append(f"{context_path.name}:\n```python\n{content}\n```")
        sections.append(f"USER TASK:\n{task}")
        if previous_error:
            sections.append(
                f"PREVIOUS ATTEMPT FAILED WITH:\n{previous_error}\n"
                "Fix that failure in the new complete file."
            )

        user_prompt = "\n\n".join(sections)
        response = self._call_ollama(system_prompt, user_prompt)
        new_source = self._extract_python_block(response)

        (target_dir / self.entry).write_text(new_source, encoding="utf-8")

    def _call_ollama(self, system: str, prompt: str) -> str:
        payload = {
            "model": self.model,
            "system": system,
            "prompt": prompt,
            "stream": False,
        }
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                details = exc.read().decode("utf-8")
            except Exception:
                details = str(exc)
            raise ImplementorError(f"Ollama request failed: {details}") from exc
        except urllib.error.URLError as exc:
            raise ImplementorError(f"Ollama is unavailable: {exc}") from exc

        result = body.get("response")
        if not isinstance(result, str) or not result.strip():
            raise ImplementorError("Ollama returned an empty response.")
        return result

    @staticmethod
    def _extract_python_block(response: str) -> str:
        match = re.search(r"```(?:python)?\s*\n(?P<code>.*?)```", response, re.DOTALL)
        if not match:
            raise ImplementorError("Model response did not contain a fenced Python block.")
        code = match.group("code").strip()
        if not code:
            raise ImplementorError("Model returned an empty Python block.")
        return code + "\n"
