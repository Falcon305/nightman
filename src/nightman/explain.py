from __future__ import annotations

from .hunt import hunt
from .models import Explanation, Failure


def _location(failure: Failure) -> str:
    if failure.location is None:
        return ""
    loc = failure.location
    return f"{loc.file}:{loc.line}" if loc.line else loc.file


def explain(target: str, *, seed: int = 0, max_examples: int = 300) -> Explanation:
    func = target.rsplit(":", 1)[-1].split(".")[-1]
    result = hunt(target, seed=seed, max_examples=max_examples)
    if result.status == "error":
        return Explanation(target=target, found=False, report=f"Could not hunt {func}: {result.message}")
    if result.status != "failing" or result.failure is None:
        return Explanation(
            target=target,
            found=False,
            report=f"The Nightman found nothing in {func} after {result.executions} tries. It stands.",
        )
    failure = result.failure
    where = _location(failure)
    where_note = f" at {where}" if where else ""
    verdict = failure.exception_type or f"{result.property} violation"
    replay = " Replayed on that input, it reproduces every time." if failure.verified else ""
    report = (
        f"{func}{where_note} breaks on {failure.args_repr}.\n"
        f"It raises {verdict}: {failure.message}.\n"
        f"Category: {failure.category} · severity {failure.severity}/5 · {failure.confidence} confidence.{replay}\n"
        f"The Nightman found it on try #{result.executions_to_first_failure} "
        f"and shrank it to a {failure.input_size}-unit input.\n"
        f"Fix: {failure.fix_hint}"
    )
    return Explanation(
        target=target,
        found=True,
        report=report,
        category=failure.category,
        severity=failure.severity,
        confidence=failure.confidence,
        fix_hint=failure.fix_hint,
    )
