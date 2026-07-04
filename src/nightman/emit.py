from __future__ import annotations

import hashlib
import os

from .models import HuntResult


def _module_and_func(target: str) -> tuple[str, str]:
    ref, qualname = target.rsplit(":", 1)
    func = qualname.split(".")[-1]
    is_path = ref.endswith(".py") or os.sep in ref
    module = os.path.splitext(os.path.basename(ref))[0] if is_path else ref
    return module, func


def _stable_id(args_repr: str) -> str:
    digest = hashlib.sha1(args_repr.encode("utf-8")).hexdigest()[:6]
    return f"nightman-{digest}"


def _literal(args: dict) -> str:
    try:
        rendered = repr(args)
        if eval(rendered) == args:
            return rendered
    except Exception:
        pass
    return repr({k: repr(v) for k, v in args.items()})


def _body(kind: str, prop: str, func: str, partner: str | None) -> list[str]:
    if prop == "roundtrip" and partner:
        return [
            "    value = next(iter(kwargs.values()))",
            f"    assert {partner}({func}(*kwargs.values())) == value",
        ]
    if prop == "idempotent":
        return [
            f"    once = {func}(*kwargs.values())",
            f"    twice = {func}(once, *list(kwargs.values())[1:])",
            "    assert once == twice",
        ]
    if prop == "differential" and partner:
        return [f"    assert {func}(**kwargs) == {partner}(**kwargs)"]
    return [f"    {func}(**kwargs)"]


def render_regression_test(result: HuntResult, partner: str | None = None) -> str:
    if result.failure is None:
        raise ValueError("cannot write a regression test without a failure")
    failure = result.failure
    module, func = _module_and_func(result.target)
    imports = [func]
    if partner and result.property in ("roundtrip", "differential"):
        imports.append(partner)
    verdict = failure.exception_type or f"{result.property} violation"
    header = [
        "# Regression test written by Nightman (github.com/Falcon305/nightman).",
        f"# The Nightman came for {func}() and it broke:",
        f"#   {failure.args_repr}",
        f"#   -> {verdict}: {failure.message}",
        "# The minimized failing input is pinned below. Delete this test once the bug is dead.",
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
        *_body(failure.kind, result.property, func, partner),
        "",
    ]
    return "\n".join(lines)


def write_regression_test(result: HuntResult, root: str = ".", partner: str | None = None) -> str:
    _, func = _module_and_func(result.target)
    source = render_regression_test(result, partner=partner)
    directory = os.path.join(root, "tests")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"test_{func}_nightman.py")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(source)
    return path
