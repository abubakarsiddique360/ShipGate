from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from shipgate.checks import FAIL, PASS, run_check
from shipgate.config import CheckSpec


def spec(check_type: str, **params) -> CheckSpec:
    return CheckSpec(type=check_type, name=check_type, params=params)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        code = 200 if self.path == "/ok" else 503
        self.send_response(code)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, *args) -> None:  # keep test output clean
        return


@pytest.fixture()
def server():
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_file_exists_pass_and_fail(tmp_path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM scratch", encoding="utf-8")
    assert run_check(spec("file_exists", path="Dockerfile"), tmp_path).status == PASS
    assert run_check(spec("file_exists", path="missing.txt"), tmp_path).status == FAIL


def test_env_present(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SHIPGATE_TEST_VALUE", "set")
    monkeypatch.delenv("SHIPGATE_TEST_MISSING", raising=False)
    assert run_check(spec("env_present", vars=["SHIPGATE_TEST_VALUE"]), tmp_path).status == PASS
    result = run_check(spec("env_present", vars=["SHIPGATE_TEST_MISSING"]), tmp_path)
    assert result.status == FAIL
    assert "SHIPGATE_TEST_MISSING" in result.detail


def test_env_present_rejects_empty_list(tmp_path) -> None:
    assert run_check(spec("env_present", vars=[]), tmp_path).status == FAIL


def test_health_check_against_local_server(server, tmp_path) -> None:
    assert run_check(spec("health", url=f"{server}/ok"), tmp_path).status == PASS
    bad = run_check(spec("health", url=f"{server}/bad"), tmp_path)
    assert bad.status == FAIL
    assert "expected HTTP 200" in bad.detail


def test_health_check_unreachable(tmp_path) -> None:
    result = run_check(spec("health", url="http://127.0.0.1:1/health", timeout=0.5), tmp_path)
    assert result.status == FAIL
    assert "unreachable" in result.detail


def test_version_match(tmp_path) -> None:
    (tmp_path / "CHANGELOG.md").write_text("## [1.4.0]\n- thing", encoding="utf-8")
    assert (
        run_check(spec("version_match", path="CHANGELOG.md", version="1.4.0"), tmp_path).status
        == PASS
    )
    assert (
        run_check(spec("version_match", path="CHANGELOG.md", version="9.9.9"), tmp_path).status
        == FAIL
    )


def test_changelog_entry_accepts_heading_formats(tmp_path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    for heading in ("## [1.4.0] - 2026-01-01", "### 1.4.0", "# v1.4.0"):
        changelog.write_text(heading, encoding="utf-8")
        assert (
            run_check(
                spec("changelog_entry", path="CHANGELOG.md", version="1.4.0"), tmp_path
            ).status
            == PASS
        )


def test_dockerfile_user_variants(tmp_path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM python:3.12\nUSER appuser\n", encoding="utf-8")
    assert run_check(spec("dockerfile_user", path="Dockerfile"), tmp_path).status == PASS

    dockerfile.write_text("FROM python:3.12\nUSER root\n", encoding="utf-8")
    assert run_check(spec("dockerfile_user", path="Dockerfile"), tmp_path).status == FAIL

    dockerfile.write_text("FROM python:3.12\n", encoding="utf-8")
    result = run_check(spec("dockerfile_user", path="Dockerfile"), tmp_path)
    assert result.status == FAIL
    assert "root" in result.detail


def test_command_check_outcomes(tmp_path) -> None:
    ok = run_check(spec("command", command="python -c pass"), tmp_path)
    assert ok.status == PASS

    failing = run_check(spec("command", command='python -c "import sys; sys.exit(3)"'), tmp_path)
    assert failing.status == FAIL
    assert "exit code 3" in failing.detail

    missing = run_check(spec("command", command="definitely-not-a-real-binary --help"), tmp_path)
    assert missing.status == FAIL
    assert "not found" in missing.detail


def test_missing_file_reports_cannot_read(tmp_path) -> None:
    assert run_check(spec("version_match", path="nope.md", version="1"), tmp_path).status == FAIL
    assert run_check(spec("dockerfile_user", path="nope"), tmp_path).status == FAIL
