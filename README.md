# ShipGate

**One command, one verdict: is this build actually safe to release?**

ShipGate runs a declarative list of readiness checks — files present, runtime
environment set, health endpoint answering, version and changelog in sync, the
container not running as root, smoke command passing — and prints a single table
plus a CI-friendly exit code. No agents, no API keys, no YAML schema.

[![CI](https://github.com/abubakarsiddique360/ShipGate/actions/workflows/ci.yml/badge.svg)](https://github.com/abubakarsiddique360/ShipGate/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.12-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)](pyproject.toml)

## Quick start

```bash
git clone https://github.com/abubakarsiddique360/ShipGate.git
cd ShipGate
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"

shipgate init                                  # write a starter shipgate.toml
DEMO_DATABASE_URL=postgres://x \
  shipgate check --config examples/demo/shipgate.toml --root examples/demo
```

```
STATUS  SEVERITY  CHECK                            DETAIL
-------------------------------------------------------------
PASS    error     Dockerfile is present            found Dockerfile
PASS    error     container does not run as root   runs as appuser
PASS    error     changelog documents 1.4.0        changelog has a heading for 1.4.0
PASS    error     version matches the changelog    found version 1.4.0
PASS    warning   runtime configuration is set     1 variable(s) set
PASS    error     smoke command exits cleanly      exit code 0

demo-api 1.4.0: PASS (6/6 checks passed, 41 ms)
```

## Configuration

```toml
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
expect_status = 200

[[check]]
type = "env_present"
vars = ["DATABASE_URL"]
severity = "warning"          # error (default) fails the gate, warning only warns
```

## Check types

| Type | Parameters | Fails when |
| --- | --- | --- |
| `file_exists` | `path` | the file is missing |
| `env_present` | `vars` | any variable is unset or empty |
| `health` | `url`, `timeout`, `expect_status` | unreachable or unexpected status |
| `version_match` | `path`, `version` | the version string is absent from the file |
| `changelog_entry` | `path`, `version` | no `## [x.y.z]` / `## x.y.z` heading |
| `dockerfile_user` | `path` | no `USER` line, or `USER root` |
| `command` | `command`, `timeout` | non-zero exit, missing binary, timeout |

Severity matters: an `error` failure exits `1` and blocks a release; a `warning`
failure only renders `WARN` and exits `0`. That keeps "nice to have" checks from
being disabled entirely — they are visible without being fatal.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | gate passed, or only warnings failed |
| `1` | at least one `error`-severity check failed |
| `2` | configuration problem (missing file, unknown check type, invalid severity) |

## Using it in CI

```yaml
- name: Release gate
  run: |
    pip install shipgate
    shipgate check --config shipgate.toml --root .
```

`--json` emits the same data as a machine-readable report for dashboards.

## Project layout

```text
src/shipgate/
├── config.py    shipgate.toml parsing + strict validation
├── checks.py    seven check implementations
├── report.py    aggregation, severity rules, table rendering
└── cli.py       check · list-types · init
examples/demo/   a working demo project
tests/           42 pytest cases
```

## Design notes

- **A failed check is data, not an exception.** Checks return a result object, so
  one broken endpoint does not hide the other six results.
- **Strict config.** Unknown check types, missing parameters and invalid
  severities fail at parse time with the offending entry number.
- **Health checks use the standard library.** `urllib` with an explicit timeout is
  enough, and it keeps the install at zero dependencies.
- **`command` checks are not shell-evaluated.** The command is split with
  `shlex`, so `&&`, pipes and redirection are not silently executed.

## Limitations

- `command` checks run arbitrary local processes. Treat a `shipgate.toml` from an
  untrusted source the same way you would treat a shell script.
- Health checks are single-shot: no retries, no backoff. Put retries in the
  orchestrator where they belong.
- This is a release *gate*, not a deployment tool. It never ships anything.

## License

[MIT](LICENSE) © 2026 **ABU BAKAR SIDDIQUE**
