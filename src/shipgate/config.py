"""Configuration for a release gate.

A project declares checks in ``shipgate.toml``::

    [project]
    name = "demo-api"
    version = "1.4.0"

    [[check]]
    type = "file_exists"
    path = "Dockerfile"

    [[check]]
    type = "health"
    url = "http://127.0.0.1:8080/health"
    timeout = 2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import tomllib

CHECK_TYPES = (
    "file_exists",
    "env_present",
    "health",
    "version_match",
    "changelog_entry",
    "dockerfile_user",
    "command",
)
SEVERITIES = ("error", "warning")

# required parameters per check type
REQUIRED = {
    "file_exists": ("path",),
    "env_present": ("vars",),
    "health": ("url",),
    "version_match": ("path", "version"),
    "changelog_entry": ("path", "version"),
    "dockerfile_user": ("path",),
    "command": ("command",),
}


class ConfigError(ValueError):
    """Raised when shipgate.toml is missing data or references an unknown check."""


@dataclass(frozen=True)
class CheckSpec:
    type: str
    name: str
    params: dict = field(default_factory=dict)
    severity: str = "error"

    def get(self, key: str, default=None):
        return self.params.get(key, default)

    def as_dict(self) -> dict:
        return {"type": self.type, "name": self.name, "severity": self.severity}


@dataclass(frozen=True)
class GateConfig:
    project: str
    version: str
    checks: tuple[CheckSpec, ...]
    path: str = ""

    @classmethod
    def from_dict(cls, data: dict, path: str = "") -> GateConfig:
        if not isinstance(data, dict):
            raise ConfigError("config root must be a table")
        project = data.get("project") or {}
        if not isinstance(project, dict):
            raise ConfigError("'project' must be a table")
        name = str(project.get("name", "")).strip()
        version = str(project.get("version", "")).strip()
        if not name:
            raise ConfigError("'project.name' is required")
        if not version:
            raise ConfigError("'project.version' is required")

        raw_checks = data.get("check")
        if not isinstance(raw_checks, list) or not raw_checks:
            raise ConfigError("at least one [[check]] entry is required")

        checks: list[CheckSpec] = []
        for index, item in enumerate(raw_checks, start=1):
            if not isinstance(item, dict):
                raise ConfigError(f"check #{index} must be a table")
            check_type = str(item.get("type", "")).strip()
            if check_type not in CHECK_TYPES:
                raise ConfigError(
                    f"check #{index} has unknown type '{check_type}' (known: {', '.join(CHECK_TYPES)})"
                )
            for required in REQUIRED[check_type]:
                if required not in item:
                    raise ConfigError(f"check #{index} ({check_type}) is missing '{required}'")
            severity = str(item.get("severity", "error")).lower()
            if severity not in SEVERITIES:
                raise ConfigError(f"check #{index} has invalid severity '{severity}'")
            name_value = str(item.get("name") or f"{check_type} #{index}")
            params = {
                key: value for key, value in item.items() if key not in {"type", "name", "severity"}
            }
            checks.append(
                CheckSpec(type=check_type, name=name_value, params=params, severity=severity)
            )

        return cls(project=name, version=version, checks=tuple(checks), path=path)

    @classmethod
    def from_toml(cls, path: Path | str) -> GateConfig:
        source = Path(path)
        try:
            data = tomllib.loads(source.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConfigError(f"config not found: {source}") from exc
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"{source.name} is not valid TOML: {exc}") from exc
        return cls.from_dict(data, path=str(source))
