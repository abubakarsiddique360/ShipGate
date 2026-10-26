"""Command-line interface for ShipGate."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from shipgate import __version__
from shipgate.checks import run_check
from shipgate.config import CHECK_TYPES, ConfigError, GateConfig
from shipgate.report import GateReport

STARTER_CONFIG = """[project]
name = "my-service"
version = "0.1.0"

[[check]]
type = "file_exists"
path = "Dockerfile"
name = "Dockerfile is present"

[[check]]
type = "dockerfile_user"
path = "Dockerfile"
name = "container does not run as root"

[[check]]
type = "changelog_entry"
path = "CHANGELOG.md"
version = "0.1.0"
name = "changelog documents this release"

[[check]]
type = "env_present"
vars = ["DATABASE_URL"]
severity = "warning"
name = "runtime configuration is set"
"""


def _check(args: argparse.Namespace) -> int:
    config = GateConfig.from_toml(args.config)
    root = Path(args.root) if args.root else Path(args.config).resolve().parent
    started = time.perf_counter()
    results = [run_check(spec, root) for spec in config.checks]
    report = GateReport(
        project=config.project,
        version=config.version,
        results=results,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        print(report.render())
    return report.exit_code


def _list_types(args: argparse.Namespace) -> int:
    for check_type in CHECK_TYPES:
        print(check_type)
    return 0


def _init(args: argparse.Namespace) -> int:
    target = Path(args.path)
    if target.exists() and not args.force:
        print(f"refusing to overwrite {target} (use --force)", file=sys.stderr)
        return 1
    target.write_text(STARTER_CONFIG, encoding="utf-8")
    print(f"wrote {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shipgate",
        description="Pre-flight release checks: files, env, health, versioning and container hardening.",
    )
    parser.add_argument("--version", action="version", version=f"shipgate {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="run the gate described by shipgate.toml")
    check.add_argument("--config", default="shipgate.toml")
    check.add_argument("--root", help="directory the relative paths are resolved against")
    check.add_argument("--json", action="store_true")
    check.set_defaults(func=_check)

    types = sub.add_parser("list-types", help="print the supported check types")
    types.set_defaults(func=_list_types)

    init = sub.add_parser("init", help="write a starter shipgate.toml")
    init.add_argument("--path", default="shipgate.toml")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
