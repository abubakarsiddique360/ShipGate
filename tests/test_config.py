from __future__ import annotations

import pytest

from shipgate.config import CHECK_TYPES, ConfigError, GateConfig


def base(**overrides) -> dict:
    data = {
        "project": {"name": "svc", "version": "1.0.0"},
        "check": [{"type": "file_exists", "path": "Dockerfile"}],
    }
    data.update(overrides)
    return data


def test_from_dict_parses_checks() -> None:
    config = GateConfig.from_dict(base())
    assert config.project == "svc"
    assert config.version == "1.0.0"
    assert config.checks[0].type == "file_exists"
    assert config.checks[0].params["path"] == "Dockerfile"
    assert config.checks[0].severity == "error"
    assert config.checks[0].name.startswith("file_exists")


def test_custom_name_and_severity_are_kept() -> None:
    config = GateConfig.from_dict(
        base(check=[{"type": "env_present", "vars": ["A"], "name": "env", "severity": "warning"}])
    )
    assert config.checks[0].name == "env"
    assert config.checks[0].severity == "warning"


def test_missing_project_name() -> None:
    with pytest.raises(ConfigError, match=r"project\.name"):
        GateConfig.from_dict(base(project={"version": "1.0.0"}))


def test_missing_version() -> None:
    with pytest.raises(ConfigError, match=r"project\.version"):
        GateConfig.from_dict(base(project={"name": "svc"}))


def test_no_checks_rejected() -> None:
    with pytest.raises(ConfigError, match="at least one"):
        GateConfig.from_dict(base(check=[]))


def test_unknown_check_type_lists_known_types() -> None:
    with pytest.raises(ConfigError) as excinfo:
        GateConfig.from_dict(base(check=[{"type": "telepathy"}]))
    assert "telepathy" in str(excinfo.value)
    assert CHECK_TYPES[0] in str(excinfo.value)


def test_missing_required_parameter() -> None:
    with pytest.raises(ConfigError, match="missing 'path'"):
        GateConfig.from_dict(base(check=[{"type": "file_exists"}]))


def test_invalid_severity_rejected() -> None:
    with pytest.raises(ConfigError, match="severity"):
        GateConfig.from_dict(base(check=[{"type": "file_exists", "path": "x", "severity": "loud"}]))


def test_non_object_check_rejected() -> None:
    with pytest.raises(ConfigError, match="check #1"):
        GateConfig.from_dict(base(check=["nope"]))


def test_from_toml_round_trip(tmp_path) -> None:
    path = tmp_path / "shipgate.toml"
    path.write_text(
        "\n".join(
            [
                "[project]",
                'name = "svc"',
                'version = "2.0.0"',
                "",
                "[[check]]",
                'type = "command"',
                'command = "python -c pass"',
            ]
        ),
        encoding="utf-8",
    )
    config = GateConfig.from_toml(path)
    assert config.version == "2.0.0"
    assert config.checks[0].type == "command"


def test_from_toml_reports_bad_toml(tmp_path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text("project = ", encoding="utf-8")
    with pytest.raises(ConfigError, match="valid TOML"):
        GateConfig.from_toml(path)
