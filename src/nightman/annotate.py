from __future__ import annotations

import os

from .models import HuntResult

_MAX_ANNOTATIONS = 10


def _escape(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _property_escape(value: str) -> str:
    return _escape(value).replace(",", "%2C").replace(":", "%3A")


def _relative(path: str) -> str:
    try:
        return os.path.relpath(path)
    except ValueError:
        return path


def _annotation(result: HuntResult) -> str | None:
    failure = result.failure
    if failure is None:
        return None
    func = result.target.rsplit(":", 1)[-1].split(".")[-1]
    file = (
        failure.location.file
        if failure.location and failure.location.file
        else _relative(result.target.rsplit(":", 1)[0])
    )
    line = failure.location.line if failure.location and failure.location.line else 1
    verdict = failure.exception_type or f"{result.property} violation"
    title = _property_escape(f"Nightman: {func} — {verdict}")
    message = _escape(f"{failure.args_repr} -> {failure.message}. {failure.fix_hint}".strip())
    return f"::error file={_property_escape(file)},line={line},title={title}::{message}"


def to_github(findings: list[HuntResult]) -> str:
    lines = []
    for result in findings[:_MAX_ANNOTATIONS]:
        annotation = _annotation(result)
        if annotation:
            lines.append(annotation)
    hidden = len(findings) - _MAX_ANNOTATIONS
    if hidden > 0:
        lines.append(f"::warning::Nightman found {hidden} more finding(s) not shown (GitHub caps annotations).")
    return "\n".join(lines)
