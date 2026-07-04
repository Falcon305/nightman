from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from typing import Any, get_origin, get_type_hints

from .models import PropertyPlan
from .target import Target

_COMMUTATIVE_NAMES = (
    "add", "plus", "sum", "combine", "merge", "union", "intersect",
    "max", "min", "gcd", "lcm", "mul", "multiply", "times", "product", "meet", "overlap",
)
_ORDER_FREE_NAMES = (
    "sum", "max", "maximum", "min", "minimum", "mean", "average", "avg",
    "total", "product", "count", "median", "mode",
)
_CONTAINER_TYPES = {
    list: "list",
    dict: "dict",
    set: "set",
    frozenset: "frozenset",
    tuple: "tuple",
    str: "str",
    bytes: "bytes",
}

_ROUNDTRIP_PAIRS: tuple[tuple[str, str], ...] = (
    (r"encode(.*)", "decode{}"),
    (r"decode(.*)", "encode{}"),
    (r"serialize(.*)", "deserialize{}"),
    (r"deserialize(.*)", "serialize{}"),
    (r"dumps?(.*)", "loads{}"),
    (r"loads?(.*)", "dumps{}"),
    (r"to_(.+)", "from_{}"),
    (r"from_(.+)", "to_{}"),
    (r"pack(.*)", "unpack{}"),
    (r"unpack(.*)", "pack{}"),
    (r"compress(.*)", "decompress{}"),
    (r"parse(.*)", "format{}"),
    (r"marshal(.*)", "unmarshal{}"),
)

_IDEMPOTENT_PREFIXES = (
    "normalize",
    "sanitize",
    "clean",
    "canonical",
    "dedupe",
    "dedup",
    "sort",
    "strip",
    "simplify",
    "collapse",
    "squeeze",
)

_RAISES = re.compile(r":raises?\s+(\w+)\s*:")
_RAISES_SECTION = re.compile(r"(?im)^\s*raises?\s*:?\s*$")


def _docstring_raises(doc: str) -> list[str]:
    found = set(_RAISES.findall(doc))
    if _RAISES_SECTION.search(doc):
        for line in doc.splitlines():
            match = re.match(r"\s+([A-Z]\w*Error|[A-Z]\w*Exception)\b", line)
            if match:
                found.add(match.group(1))
    return sorted(found)


def _required_positional(func: Any) -> list[str]:
    try:
        signature = inspect.signature(func)
    except (ValueError, TypeError):
        return []
    names = []
    for name, param in signature.parameters.items():
        if name == "self" or param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        names.append(name)
    return names


def _find_inverse(target: Target, siblings: dict[str, Any]) -> str | None:
    name = target.qualname.split(".")[-1]
    for pattern, template in _ROUNDTRIP_PAIRS:
        match = re.fullmatch(pattern, name)
        if not match:
            continue
        candidate = template.format(*match.groups())
        if candidate in siblings and candidate != name:
            return candidate
    return None


def _looks_idempotent(func: Any) -> bool:
    name = getattr(func, "__name__", "").lower()
    return any(name.startswith(prefix) for prefix in _IDEMPOTENT_PREFIXES)


def _hints(func: Any) -> dict[str, Any]:
    try:
        return get_type_hints(func)
    except Exception:
        return {}


def _looks_commutative(func: Any, args: list[str]) -> bool:
    if len(args) != 2:
        return False
    hints = _hints(func)
    if args[0] not in hints or args[1] not in hints or hints[args[0]] != hints[args[1]]:
        return False
    name = getattr(func, "__name__", "").lower()
    return any(key in name for key in _COMMUTATIVE_NAMES)


def _looks_order_free(func: Any, args: list[str]) -> bool:
    if len(args) != 1:
        return False
    name = getattr(func, "__name__", "").lower()
    return any(name == key or name.startswith(f"{key}_") or name.endswith(f"_{key}") for key in _ORDER_FREE_NAMES)


def _return_container(func: Any) -> str | None:
    ret = _hints(func).get("return")
    if ret is None:
        return None
    origin = get_origin(ret) or ret
    return _CONTAINER_TYPES.get(origin)


def choose_properties(target: Target, siblings: dict[str, Any]) -> list[PropertyPlan]:
    func = target.func
    allowed = _docstring_raises(func.__doc__ or "")
    args = _required_positional(func)
    plans: list[PropertyPlan] = []
    partner = _find_inverse(target, siblings)
    if partner and len(args) == 1:
        plans.append(
            PropertyPlan(
                name="roundtrip",
                partner=partner,
                allowed_exceptions=allowed,
                description=f"{partner}({func.__name__}(x)) == x",
            )
        )
    if _looks_idempotent(func) and args:
        plans.append(
            PropertyPlan(
                name="idempotent",
                feedback_arg=args[0],
                allowed_exceptions=allowed,
                description=f"{func.__name__}({func.__name__}(x)) == {func.__name__}(x)",
            )
        )
    if _looks_commutative(func, args):
        plans.append(
            PropertyPlan(name="commutative", allowed_exceptions=allowed, description="f(a, b) == f(b, a)")
        )
    if _looks_order_free(func, args):
        plans.append(
            PropertyPlan(name="permutation", allowed_exceptions=allowed, description="f(xs) == f(reversed xs)")
        )
    container = _return_container(func)
    if container:
        plans.append(
            PropertyPlan(
                name="type-contract", allowed_exceptions=allowed, description=f"returns a {container}"
            )
        )
    plans.append(
        PropertyPlan(
            name="never-raises",
            allowed_exceptions=allowed,
            description=f"{func.__name__}(x) does not raise an unexpected exception",
        )
    )
    return plans


class PropertyViolation(AssertionError):
    pass


def _allowed_tuple(names: list[str]) -> frozenset[str]:
    return frozenset(names)


def build_check(func: Any, plan: PropertyPlan, partner: Any | None) -> Callable[..., None]:
    allowed = _allowed_tuple(plan.allowed_exceptions)
    names = _required_positional(func)
    first_arg = names[0] if names else None

    def _guard(exc: BaseException) -> bool:
        return type(exc).__name__ in allowed

    if plan.name == "never-raises":

        def check_never(**kwargs: Any) -> None:
            try:
                func(**kwargs)
            except Exception as exc:
                if _guard(exc):
                    return
                raise

        return check_never

    if plan.name == "idempotent":

        def check_idempotent(**kwargs: Any) -> None:
            try:
                first = func(**kwargs)
                feedback = dict(kwargs)
                if first_arg is not None:
                    feedback[first_arg] = first
                second = func(**feedback)
            except Exception as exc:
                if _guard(exc):
                    return
                raise
            if first != second:
                raise PropertyViolation(f"not idempotent: f(f(x))={second!r} != f(x)={first!r}")

        return check_idempotent

    if plan.name == "roundtrip":

        def check_roundtrip(**kwargs: Any) -> None:
            if first_arg is None or partner is None:
                return
            value = kwargs[first_arg]
            try:
                decoded = partner(func(**kwargs))
            except Exception as exc:
                if _guard(exc):
                    return
                raise
            if decoded != value:
                raise PropertyViolation(f"roundtrip broke: partner(f(x))={decoded!r} != x={value!r}")

        return check_roundtrip

    if plan.name == "differential":

        def check_differential(**kwargs: Any) -> None:
            if partner is None:
                return
            left = _outcome(func, kwargs)
            right = _outcome(partner, kwargs)
            if left != right:
                raise PropertyViolation(f"differs: target={left!r} reference={right!r}")

        return check_differential

    if plan.name == "commutative":

        def check_commutative(**kwargs: Any) -> None:
            values = list(kwargs.values())
            try:
                forward = func(**kwargs)
                backward = func(*reversed(values))
            except Exception as exc:
                if _guard(exc):
                    return
                raise
            if forward != backward:
                raise PropertyViolation(f"not commutative: f(a,b)={forward!r} != f(b,a)={backward!r}")

        return check_commutative

    if plan.name == "permutation":

        def check_permutation(**kwargs: Any) -> None:
            values = list(kwargs.values())
            sequence = values[0]
            if not isinstance(sequence, (list, tuple)):
                return
            try:
                base = func(**kwargs)
                shuffled = func(*[list(reversed(sequence)), *values[1:]])
            except Exception as exc:
                if _guard(exc):
                    return
                raise
            if base != shuffled:
                raise PropertyViolation(f"order-dependent: f(xs)={base!r} != f(reversed xs)={shuffled!r}")

        return check_permutation

    if plan.name == "type-contract":
        ret = _hints(func).get("return")
        expected = get_origin(ret) or ret

        def check_type_contract(**kwargs: Any) -> None:
            try:
                result = func(**kwargs)
            except Exception as exc:
                if _guard(exc):
                    return
                raise
            if expected is not None and not isinstance(result, expected):
                raise PropertyViolation(
                    f"returned {type(result).__name__}, but annotated to return {getattr(expected, '__name__', expected)}"
                )

        return check_type_contract

    raise ValueError(f"unknown property {plan.name}")


def _outcome(func: Any, kwargs: dict) -> Any:
    try:
        return ("value", func(**kwargs))
    except Exception as exc:
        return ("raised", type(exc).__name__)
