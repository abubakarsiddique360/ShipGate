from __future__ import annotations

import json

from shipgate.checks import FAIL, PASS, CheckResult
from shipgate.report import GateReport


def result(status: str, severity: str = "error", name: str = "check") -> CheckResult:
    return CheckResult(
        name=name, check_type="file_exists", status=status, detail="detail", severity=severity
    )


def test_all_pass() -> None:
    report = GateReport("svc", "1.0.0", [result(PASS), result(PASS)])
    assert report.status == "pass"
    assert report.exit_code == 0


def test_error_failure_fails_the_gate() -> None:
    report = GateReport("svc", "1.0.0", [result(PASS), result(FAIL)])
    assert report.status == "fail"
    assert report.exit_code == 1
    assert len(report.error_failures) == 1


def test_warning_failure_only_warns() -> None:
    report = GateReport("svc", "1.0.0", [result(PASS), result(FAIL, severity="warning")])
    assert report.status == "warn"
    assert report.exit_code == 0
    assert report.warning_failures


def test_error_beats_warning() -> None:
    report = GateReport("svc", "1.0.0", [result(FAIL, severity="warning"), result(FAIL)])
    assert report.status == "fail"


def test_render_contains_every_check() -> None:
    report = GateReport("svc", "2.1.0", [result(PASS, name="alpha"), result(FAIL, name="beta")])
    rendered = report.render()
    assert "alpha" in rendered
    assert "beta" in rendered
    assert "FAIL" in rendered
    assert "svc 2.1.0: FAIL" in rendered


def test_as_dict_is_serialisable() -> None:
    report = GateReport("svc", "1.0.0", [result(PASS)], duration_ms=12)
    payload = json.loads(json.dumps(report.as_dict()))
    assert payload["status"] == "pass"
    assert payload["checks"][0]["status"] == "pass"
    assert payload["duration_ms"] == 12
