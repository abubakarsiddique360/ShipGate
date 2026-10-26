"""Aggregate results into a gate decision and a printable table."""

from __future__ import annotations

from dataclasses import dataclass, field

from shipgate.checks import FAIL, CheckResult

PASS = "pass"
WARN = "warn"
FAIL_STATUS = "fail"


@dataclass
class GateReport:
    project: str
    version: str
    results: list[CheckResult] = field(default_factory=list)
    duration_ms: int = 0

    @property
    def failures(self) -> list[CheckResult]:
        return [result for result in self.results if result.status == FAIL]

    @property
    def error_failures(self) -> list[CheckResult]:
        return [result for result in self.failures if result.severity == "error"]

    @property
    def warning_failures(self) -> list[CheckResult]:
        return [result for result in self.failures if result.severity == "warning"]

    @property
    def status(self) -> str:
        if self.error_failures:
            return FAIL_STATUS
        if self.warning_failures:
            return WARN
        return PASS

    @property
    def exit_code(self) -> int:
        return 1 if self.status == FAIL_STATUS else 0

    def as_dict(self) -> dict:
        return {
            "project": self.project,
            "version": self.version,
            "status": self.status,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "checks": [result.as_dict() for result in self.results],
        }

    def render(self) -> str:
        rows = [("STATUS", "SEVERITY", "CHECK", "DETAIL")]
        symbols = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}
        for result in self.results:
            rows.append(
                (
                    symbols.get(result.status, result.status.upper()),
                    result.severity,
                    result.name,
                    result.detail,
                )
            )
        widths = [max(len(row[index]) for row in rows) for index in range(4)]
        lines = ["  ".join(cell.ljust(widths[index]) for index, cell in enumerate(rows[0]))]
        lines.append("-" * (sum(widths) + 6))
        for row in rows[1:]:
            lines.append("  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))
        passed = sum(1 for result in self.results if result.status != FAIL)
        lines.append("")
        lines.append(
            f"{self.project} {self.version}: {self.status.upper()} "
            f"({passed}/{len(self.results)} checks passed, {self.duration_ms} ms)"
        )
        return "\n".join(lines)
