from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from .implementor import Implementor, OllamaImplementor
from .paths import AppPaths
from .probe import Probe, ProcessAliveProbe
from .runner import PythonRunner, Runner
from .validator import CompilePythonValidator, TokenPolicyValidator, Validator


@dataclass
class AppSpec:
    name: str
    paths: AppPaths
    entry: str
    seed_version: str
    runner: Runner
    probe: Probe
    validators: list[Validator]
    implementor: Implementor
    max_attempts: int


def load_spec(config_path: Path | str) -> AppSpec:
    config_path = Path(config_path).resolve()
    if config_path.is_dir():
        config_path = config_path / "forge.toml"
    if not config_path.exists():
        raise FileNotFoundError(f"forge config not found: {config_path}")

    with config_path.open("rb") as f:
        raw = tomllib.load(f)

    app_root = config_path.parent
    name = _require_str(raw, "name")
    entry = raw.get("entry", "main.py")
    seed_version = raw.get("seed_version", "v0")
    paths = AppPaths.from_root(app_root)

    runner = _build_runner(raw.get("runner", {}))
    probe = _build_probe(raw.get("probe", {}))
    implementor_config = raw.get("implementor", {})
    implementor = _build_implementor(implementor_config, app_root, entry)
    validators = _build_validators(raw, entry)
    max_attempts = int(implementor_config.get("max_attempts", 3))

    return AppSpec(
        name=name,
        paths=paths,
        entry=entry,
        seed_version=seed_version,
        runner=runner,
        probe=probe,
        validators=validators,
        implementor=implementor,
        max_attempts=max_attempts,
    )


def _require_str(raw: dict, key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str):
        raise ValueError(f"forge.toml missing required string field: {key}")
    return value


def _build_runner(config: dict) -> Runner:
    kind = config.get("kind", "python")
    if kind == "python":
        return PythonRunner(require_tk=False)
    if kind == "python-tk":
        return PythonRunner(require_tk=True)
    raise ValueError(f"Unknown runner kind: {kind}")


def _build_probe(config: dict) -> Probe:
    kind = config.get("kind", "process-alive")
    if kind == "process-alive":
        return ProcessAliveProbe(
            window_seconds=float(config.get("window_seconds", 10.0)),
        )
    raise ValueError(f"Unknown probe kind: {kind}")


def _build_implementor(config: dict, app_root: Path, entry: str) -> Implementor:
    kind = config.get("kind", "ollama")
    if kind == "ollama":
        prompt_path = app_root / config.get("prompt", "prompt.md")
        if not prompt_path.exists():
            raise FileNotFoundError(f"Implementor prompt not found: {prompt_path}")
        return OllamaImplementor(
            model=config.get("model", "gemma4:latest"),
            prompt_path=prompt_path,
            entry=entry,
            url=config.get("url", "http://localhost:11434/api/generate"),
        )
    raise ValueError(f"Unknown implementor kind: {kind}")


def _build_validators(raw: dict, entry: str) -> list[Validator]:
    validators: list[Validator] = [CompilePythonValidator(entry=entry)]

    validator_section = raw.get("validator", {})
    token_policy = validator_section.get("token_policy")
    if token_policy:
        validators.append(
            TokenPolicyValidator(
                entry=entry,
                forbidden=list(token_policy.get("forbidden", [])),
                required=list(token_policy.get("required", [])),
            )
        )

    return validators
