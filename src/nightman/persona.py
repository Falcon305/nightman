from __future__ import annotations

from .models import HuntResult

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
            f"  input:    {failure.args_repr}",
            f"  detail:   {failure.message}{where}",
            f"  property: {result.property}",
            f"  size:     {failure.input_size} (found at execution {result.executions_to_first_failure})",
        ]
        return "\n".join(lines)

    shrink_note = ""
    if result.shrink_executions:
        shrink_note = f"\n   shrunk to its smallest form in {result.shrink_executions} more."
    lines = [
        "🌙 THE NIGHTMAN COMETH.",
        f"   He came for {func}() with:  {failure.args_repr}",
        f"   → {verdict}: {failure.message}{where}",
        f"   found on try #{result.executions_to_first_failure}.{shrink_note}",
    ]
    return "\n".join(lines)
