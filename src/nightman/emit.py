from __future__ import annotations

import hashlib
import math
import os

from . import __version__
from .models import HuntResult


def _dotted_module(target: str) -> tuple[str, str]:
    ref, qualname = target.rsplit(":", 1)
    func = qualname.split(".")[-1]
    if not (ref.endswith(".py") or os.sep in ref):
        return ref, func
    directory = os.path.dirname(os.path.abspath(ref))
    parts = [os.path.splitext(os.path.basename(ref))[0]]
    while os.path.exists(os.path.join(directory, "__init__.py")):
        parts.append(os.path.basename(directory))
        directory = os.path.dirname(directory)
    return ".".join(reversed(parts)), func


def _stable_id(args_repr: str) -> str:
    digest = hashlib.sha1(args_repr.encode("utf-8")).hexdigest()[:6]
    return f"nightman-{digest}"


def _render(value: object) -> str:
    if isinstance(value, bool) or value is None:
        return repr(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "float('nan')"
        if math.isinf(value):
            return "float('inf')" if value > 0 else "float('-inf')"
        return repr(value)
    if isinstance(value, (int, str, bytes)):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_render(v) for v in value) + "]"
    if isinstance(value, tuple):
        inner = ", ".join(_render(v) for v in value)
        return f"({inner},)" if len(value) == 1 else f"({inner})"
    if isinstance(value, (set, frozenset)):
        return "{" + ", ".join(_render(v) for v in value) + "}" if value else "set()"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_render(k)}: {_render(v)}" for k, v in value.items()) + "}"
    return repr(value)


def _literal(args: dict) -> str:
    return "{" + ", ".join(f"{key!r}: {_render(value)}" for key, value in args.items()) + "}"


def _body(result: HuntResult, func: str, partner: str | None) -> list[str]:
    failure = result.failure
    assert failure is not None
    prop = result.property
    if failure.kind == "crash":
        return [f"    {func}(**kwargs)"]
    if prop == "differential" and partner:
        return [f"    assert {func}(**kwargs) == {partner}(**kwargs)"]
    if prop == "roundtrip" and partner:
        return [f"    assert {partner}({func}(**kwargs)) == next(iter(kwargs.values()))"]
    if prop == "idempotent":
        return [
            f"    once = {func}(**kwargs)",
            f"    assert once == {func}(once, *list(kwargs.values())[1:])",
        ]
    if prop == "commutative":
        return [
            "    values = list(kwargs.values())",
            f"    assert {func}(**kwargs) == {func}(*reversed(values))",
        ]
    if prop == "permutation":
        return [
            "    values = list(kwargs.values())",
            "    reordered = [list(reversed(values[0])), *values[1:]]",
            f"    assert {func}(**kwargs) == {func}(*reordered)",
        ]
    if prop == "type-contract" and failure.expected_type:
        return [f"    assert isinstance({func}(**kwargs), {failure.expected_type})"]
    return [f"    {func}(**kwargs)"]


def render_regression_test(result: HuntResult, partner: str | None = None) -> str:
    if result.failure is None:
        raise ValueError("cannot write a regression test without a failure")
    failure = result.failure
    module, func = _dotted_module(result.target)
    imports = [func]
    if partner and result.property in ("roundtrip", "differential"):
        imports.append(partner)
    verdict = failure.exception_type or f"{result.property} violation"
    header = [
        "# Regression test written by Nightman (github.com/Falcon305/nightman).",
        f"# The Nightman came for {func}() and it broke:",
        f"#   {failure.args_repr}",
        f"#   -> {verdict}: {failure.message}",
        f"# Pinned with nightman {__version__}, seed {result.seed}. Delete once the bug is dead.",
    ]
    lines = [
        *header,
        "import pytest",
        "",
        f"from {module} import {', '.join(imports)}",
        "",
        "",
        "@pytest.mark.parametrize(",
        '    "kwargs",',
        "    [",
        f"        pytest.param({_literal(failure.args)}, id={_stable_id(failure.args_repr)!r}),",
        "    ],",
        ")",
        f"def test_{func}_nightman(kwargs):",
        *_body(result, func, partner),
        "",
    ]
    return "\n".join(lines)


def write_regression_test(result: HuntResult, root: str = ".", partner: str | None = None) -> str:
    _, func = _dotted_module(result.target)
    source = render_regression_test(result, partner=partner)
    directory = os.path.join(root, "tests")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"test_{func}_nightman.py")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(source)
    return path
