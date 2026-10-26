from __future__ import annotations

import json
import os
from pathlib import Path

from shipgate.cli import main

DEMO = Path(__file__).resolve().parent.parent / "examples" / "demo"


def test_demo_gate_passes(capsys, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_DATABASE_URL", "postgres://example")
    code = main(["check", "--config", str(DEMO / "shipgate.toml"), "--root", str(DEMO)])
    out = capsys.readouterr().out
    assert code == 0
    assert "PASS" in out
    assert "demo-api 1.4.0" in out


def test_missing_env_produces_warning_not_failure(capsys, monkeypatch) -> None:
    monkeypatch.delenv("DEMO_DATABASE_URL", raising=False)
    code = main(["check", "--config", str(DEMO / "shipgate.toml"), "--root", str(DEMO)])
    out = capsys.readouterr().out
    assert code == 0
    assert "WARN" in out


def test_json_output(tmp_path, capsys) -> None:
    config = tmp_path / "shipgate.toml"
    config.write_text(
        "\n".join(
            [
                "[project]",
                'name = "svc"',
                'version = "1.0.0"',
                "",
                "[[check]]",
                'type = "file_exists"',
                'path = "present.txt"',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "present.txt").write_text("here", encoding="utf-8")
    assert main(["check", "--config", str(config), "--root", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "pass"
    assert payload["checks"][0]["type"] == "file_exists"


def test_failed_check_exits_one(tmp_path, capsys) -> None:
    config = tmp_path / "shipgate.toml"
    config.write_text(
        "\n".join(
            [
                "[project]",
                'name = "svc"',
                'version = "1.0.0"',
                "",
                "[[check]]",
                'type = "file_exists"',
                'path = "missing.txt"',
            ]
        ),
        encoding="utf-8",
    )
    assert main(["check", "--config", str(config), "--root", str(tmp_path)]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_missing_config_exits_two(tmp_path, capsys) -> None:
    assert main(["check", "--config", str(tmp_path / "nope.toml")]) == 2
    assert "error" in capsys.readouterr().err


def test_list_types(capsys) -> None:
    assert main(["list-types"]) == 0
    types = capsys.readouterr().out.split()
    assert "file_exists" in types
    assert "health" in types


def test_init_writes_starter_config(tmp_path, capsys) -> None:
    target = tmp_path / "shipgate.toml"
    assert main(["init", "--path", str(target)]) == 0
    assert "project" in target.read_text(encoding="utf-8")
    assert "wrote" in capsys.readouterr().out

    assert main(["init", "--path", str(target)]) == 1
    assert main(["init", "--path", str(target), "--force"]) == 0


def test_relative_root_defaults_to_config_directory(capsys, monkeypatch) -> None:
    monkeypatch.chdir(os.path.dirname(DEMO))
    monkeypatch.setenv("DEMO_DATABASE_URL", "postgres://example")
    assert main(["check", "--config", str(DEMO / "shipgate.toml")]) == 0
