"""The individual checks.

Each check is a small pure-ish function that returns a :class:`CheckResult` and
never raises for an expected failure — a failing check is data, not an exception.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from shipgate.config import CheckSpec

PASS = "pass"
FAIL = "fail"
SKIP = "skip"


@dataclass(frozen=True)
class CheckResult:
    name: str
    check_type: str
    status: str
    detail: str
    severity: str = "error"
    duration_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.status != FAIL

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.check_type,
            "status": self.status,
            "severity": self.severity,
            "detail": self.detail,
            "duration_ms": self.duration_ms,
        }


def _result(spec: CheckSpec, status: str, detail: str, started: float) -> CheckResult:
    return CheckResult(
        name=spec.name,
        check_type=spec.type,
        status=status,
        detail=detail,
        severity=spec.severity,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


def check_file_exists(spec: CheckSpec, root: Path) -> CheckResult:
    started = time.perf_counter()
    target = root / str(spec.get("path"))
    if target.exists():
        return _result(spec, PASS, f"found {spec.get('path')}", started)
    return _result(spec, FAIL, f"missing {spec.get('path')}", started)


def check_env_present(spec: CheckSpec, root: Path) -> CheckResult:
    started = time.perf_counter()
    names = spec.get("vars") or []
    if not isinstance(names, list) or not names:
        return _result(spec, FAIL, "'vars' must be a non-empty list", started)
    missing = [name for name in names if not os.environ.get(str(name), "").strip()]
    if missing:
        return _result(spec, FAIL, f"missing or empty: {', '.join(missing)}", started)
    return _result(spec, PASS, f"{len(names)} variable(s) set", started)


def check_health(spec: CheckSpec, root: Path) -> CheckResult:
    started = time.perf_counter()
    url = str(spec.get("url"))
    timeout = float(spec.get("timeout", 3))
    expected = int(spec.get("expect_status", 200))
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return _result(spec, FAIL, f"unreachable: {exc}", started)
    if status == expected:
        return _result(spec, PASS, f"HTTP {status}", started)
    return _result(spec, FAIL, f"expected HTTP {expected}, got {status}", started)


def _read(root: Path, spec: CheckSpec) -> str | None:
    path = root / str(spec.get("path"))
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def check_version_match(spec: CheckSpec, root: Path) -> CheckResult:
    started = time.perf_counter()
    version = str(spec.get("version"))
    text = _read(root, spec)
    if text is None:
        return _result(spec, FAIL, f"cannot read {spec.get('path')}", started)
    if version in text:
        return _result(spec, PASS, f"found version {version}", started)
    return _result(spec, FAIL, f"version {version} not found in {spec.get('path')}", started)


def check_changelog_entry(spec: CheckSpec, root: Path) -> CheckResult:
    started = time.perf_counter()
    version = str(spec.get("version"))
    text = _read(root, spec)
    if text is None:
        return _result(spec, FAIL, f"cannot read {spec.get('path')}", started)
    pattern = re.compile(rf"^#{{1,3}}\s*\[?v?{re.escape(version)}\]?", re.MULTILINE)
    if pattern.search(text):
        return _result(spec, PASS, f"changelog has a heading for {version}", started)
    return _result(spec, FAIL, f"no changelog heading for {version}", started)


def check_dockerfile_user(spec: CheckSpec, root: Path) -> CheckResult:
    started = time.perf_counter()
    text = _read(root, spec)
    if text is None:
        return _result(spec, FAIL, f"cannot read {spec.get('path')}", started)
    users = re.findall(r"^\s*USER\s+(\S+)", text, flags=re.MULTILINE | re.IGNORECASE)
    if not users:
        return _result(spec, FAIL, "no USER instruction; the image would run as root", started)
    non_root = [user for user in users if user.lower() not in {"root", "0", "0:0"}]
    if not non_root:
        return _result(spec, FAIL, f"USER is root ({users[-1]})", started)
    return _result(spec, PASS, f"runs as {non_root[-1]}", started)


def check_command(spec: CheckSpec, root: Path) -> CheckResult:
    started = time.perf_counter()
    command = str(spec.get("command"))
    timeout = float(spec.get("timeout", 30))
    try:
        completed = subprocess.run(
            shlex.split(command),
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return _result(spec, FAIL, f"command not found: {shlex.split(command)[0]}", started)
    except subprocess.TimeoutExpired:
        return _result(spec, FAIL, f"timed out after {timeout}s", started)
    if completed.returncode == 0:
        return _result(spec, PASS, "exit code 0", started)
    tail = (completed.stderr or completed.stdout or "").strip().splitlines()
    return _result(
        spec,
        FAIL,
        f"exit code {completed.returncode}: {tail[-1] if tail else 'no output'}",
        started,
    )


CHECK_FUNCTIONS = {
    "file_exists": check_file_exists,
    "env_present": check_env_present,
    "health": check_health,
    "version_match": check_version_match,
    "changelog_entry": check_changelog_entry,
    "dockerfile_user": check_dockerfile_user,
    "command": check_command,
}


def run_check(spec: CheckSpec, root: Path) -> CheckResult:
    return CHECK_FUNCTIONS[spec.type](spec, root)
