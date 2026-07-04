from __future__ import annotations

from typing import TYPE_CHECKING

from .models import HuntResult

if TYPE_CHECKING:
    from .models import ScanReport

_CLEAN = "☀️ Dayman holds. The Nightman threw {execs} inputs at {func}() and it stood."
_CLEAN_PLAIN = "PASS: no failing input found for {func} in {execs} executions."
_ERROR = "🌫️ {message}"


def _func_name(target: str) -> str:
    return target.rsplit(":", 1)[-1].split(".")[-1]


def _location(result: HuntResult) -> str:
    if result.failure is None or result.failure.location is None:
        return ""
    loc = result.failure.location
    if loc.line:
        return f"{loc.file}:{loc.line}"
    return loc.file


def render_hunt(result: HuntResult, mode: str = "nightman") -> str:
    func = _func_name(result.target)
    if result.status == "error":
        return _ERROR.format(message=result.message) if mode == "nightman" else f"ERROR: {result.message}"
    if result.status == "clean":
        template = _CLEAN if mode == "nightman" else _CLEAN_PLAIN
        return template.format(execs=result.executions, func=func)

    failure = result.failure
    assert failure is not None
    verdict = failure.exception_type or f"{result.property} violation"
    location = _location(result)
    where = f" at {location}" if location else ""

    if mode == "plain":
        lines = [
            f"FAIL: {func} — {verdict}",
            f"  input:      {failure.args_repr}",
            f"  detail:     {failure.message}{where}",
            f"  category:   {failure.category} (severity {failure.severity}/5, {failure.confidence})",
            f"  size:       {failure.input_size} (found at execution {result.executions_to_first_failure})",
        ]
        return "\n".join(lines)

    shrink_note = ""
    if result.shrink_executions:
        shrink_note = f"\n   shrunk to its smallest form in {result.shrink_executions} more."
    verified_note = " (replayed — it reproduces)" if failure.verified else ""
    lines = [
        "🌙 THE NIGHTMAN COMETH.",
        f"   He came for {func}() with:  {failure.args_repr}",
        f"   → {verdict}: {failure.message}{where}",
        f"   {failure.category}, severity {failure.severity}/5, {failure.confidence} confidence{verified_note}.",
        f"   found on try #{result.executions_to_first_failure}.{shrink_note}",
    ]
    return "\n".join(lines)


def _finding_row(result: HuntResult) -> str:
    failure = result.failure
    assert failure is not None
    func = _func_name(result.target)
    verdict = failure.exception_type or f"{result.property} violation"
    return f"  [{failure.severity}/{failure.confidence:<9}] {func:<24} {verdict:<20} {failure.args_repr}"


def render_scan(report: ScanReport, mode: str = "nightman") -> str:
    dedup_note = f" ({report.deduped} duplicate crash site(s) collapsed)" if report.deduped else ""
    if mode == "plain":
        head = (
            f"Scanned {report.scanned} function(s) in {report.root} — "
            f"{len(report.findings)} broke, {report.clean} held, grade {report.grade}.{dedup_note}"
        )
        return "\n".join([head, *(_finding_row(r) for r in report.findings)])

    if not report.findings:
        return (
            f"☀️ Dayman wins. The Nightman came for {report.scanned} function(s) in {report.root} "
            f"and not one of them broke. Grade {report.grade}."
        )
    header = [
        f"🌙 THE NIGHTMAN CAME FOR {report.scanned} FUNCTION(S). He broke {len(report.findings)}.{dedup_note}",
        f"   Grade {report.grade}. Worst first:",
    ]
    body = [_finding_row(r) for r in report.findings[:20]]
    tail = []
    if len(report.findings) > 20:
        tail = [f"   … and {len(report.findings) - 20} more. Filter by confidence or scan a smaller path."]
    return "\n".join([*header, *body, *tail])
