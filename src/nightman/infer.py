from __future__ import annotations

import inspect
from typing import Any, get_type_hints

import hypothesis.strategies as st

CHAOS = st.one_of(
    st.none(),
    st.booleans(),
    st.sampled_from([0, 1, -1, 2, 255, 256, 2**31, -(2**31), 2**63 - 1, -(2**63)]),
    st.integers(),
    st.floats(allow_nan=True, allow_infinity=True),
    st.sampled_from(["", " ", "0", "-1", "\x00", "\n", "𝕦𝕟𝕚𝕔𝕠𝕕𝕖", "﷽", "🧨", "\ud83d", "\N{BOM}"]),
    st.text(),
    st.text(min_size=1024, max_size=1024),
    st.sampled_from([[], {}, set(), (), b""]),
    st.binary(),
    st.lists(st.integers()),
    st.dictionaries(st.text(max_size=8), st.integers()),
)

_NAME_HINTS: dict[tuple[str, ...], Any] = {
    ("path", "filename", "filepath", "file", "dir", "directory"): st.text(),
    ("count", "n", "num", "size", "length", "limit", "k"): st.integers(min_value=-1, max_value=10_000),
    ("index", "idx", "pos", "offset", "i", "j"): st.integers(min_value=-5, max_value=10_000),
    ("pattern", "regex"): st.from_regex(r"\w{0,8}", fullmatch=True),
    ("seed",): st.integers(),
    ("name", "key", "label", "title", "text", "value", "s"): st.text(),
    ("data", "payload", "body"): st.one_of(st.text(), st.binary()),
}


def _by_name(name: str) -> Any | None:
    lowered = name.lower()
    for names, strategy in _NAME_HINTS.items():
        if lowered in names:
            return strategy
    return None


def _from_default(value: Any) -> Any | None:
    if isinstance(value, bool):
        return st.booleans()
    if isinstance(value, int):
        return st.integers()
    if isinstance(value, float):
        return st.floats(allow_nan=True, allow_infinity=True)
    if isinstance(value, str):
        return st.text()
    if isinstance(value, bytes):
        return st.binary()
    if isinstance(value, (list, tuple)):
        return st.lists(CHAOS, max_size=8)
    if isinstance(value, dict):
        return st.dictionaries(st.text(max_size=8), CHAOS, max_size=8)
    return None


def _fallback(name: str, param: inspect.Parameter) -> Any:
    if param.default is not inspect.Parameter.empty and param.default is not None:
        guessed = _from_default(param.default)
        if guessed is not None:
            return guessed
    named = _by_name(name)
    if named is not None:
        return named
    return CHAOS


def _hints_for(func: Any) -> dict[str, Any]:
    try:
        return get_type_hints(func)
    except Exception:
        return {}


def strategies_for(func: Any) -> dict[str, Any]:
    signature = inspect.signature(func)
    hints = _hints_for(func)
    plans: dict[str, Any] = {}
    for name, param in signature.parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        if name == "self":
            continue
        if name in hints:
            try:
                plans[name] = st.from_type(hints[name])
                continue
            except Exception:
                pass
        plans[name] = _fallback(name, param)
    return plans


def kwargs_strategy(func: Any) -> Any:
    return st.fixed_dictionaries(strategies_for(func))


def describe_strategies(func: Any) -> dict[str, str]:
    signature = inspect.signature(func)
    hints = _hints_for(func)
    described: dict[str, str] = {}
    for name, param in signature.parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD) or name == "self":
            continue
        if name in hints:
            described[name] = f"from_type({getattr(hints[name], '__name__', hints[name])})"
        elif param.default is not inspect.Parameter.empty and param.default is not None:
            described[name] = f"from default {type(param.default).__name__}"
        elif _by_name(name) is not None:
            described[name] = "name heuristic"
        else:
            described[name] = "chaos corpus"
    return described
