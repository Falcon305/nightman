from __future__ import annotations

import os
from typing import Any

from hypothesis import HealthCheck, given, seed, settings

from .infer import kwargs_strategy
from .models import Failure, HuntResult, Location, PropertyPlan
from .properties import build_check, choose_properties
from .sandbox import call_timeout, run_in_subprocess
from .target import load_target, reload_from_origin, sibling_functions

_ENGINE_FILES = ("properties.py", "hunt.py", "sandbox.py", "infer.py")


def _size(value: Any) -> int:
    if isinstance(value, bool):
        return 1
    if isinstance(value, int):
        return min(len(str(abs(value))), 40)
    if isinstance(value, (str, bytes)):
        return len(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return len(value) + sum(_size(v) for v in list(value)[:50])
    if isinstance(value, dict):
        return len(value) + sum(_size(v) for v in list(value.values())[:50])
    return 1


def _kwargs_size(kwargs: dict) -> int:
    return sum(_size(v) for v in kwargs.values())


def _args_repr(func_name: str, kwargs: dict) -> str:
    parts = []
    for name, value in kwargs.items():
        try:
            rendered = repr(value)
        except Exception:
            rendered = f"<{type(value).__name__}>"
        parts.append(f"{name}={rendered}")
    return f"{func_name}({', '.join(parts)})"


def _location(exc: BaseException) -> Location | None:
    frames = []
    tb = exc.__traceback__
    while tb is not None:
        frames.append(tb)
        tb = tb.tb_next
    for tb in reversed(frames):
        code = tb.tb_frame.f_code
        filename = code.co_filename.replace(os.sep, "/")
        if "/nightman/" in filename and any(filename.endswith(name) for name in _ENGINE_FILES):
            continue
        return Location(file=os.path.basename(code.co_filename), line=tb.tb_lineno, func=code.co_name)
    return None


def _run_property(
    func: Any,
    plan: PropertyPlan,
    partner: Any | None,
    target_spec: str,
    seed_value: int,
    max_examples: int,
    per_example: float,
) -> HuntResult:
    check = build_check(func, plan, partner)
    strategy = kwargs_strategy(func)
    stats: dict[str, Any] = {"execs": 0, "first_fail": None}
    captured: dict[str, Any] = {}

    @seed(seed_value)
    @settings(
        max_examples=max_examples,
        database=None,
        deadline=None,
        suppress_health_check=list(HealthCheck),
    )
    @given(kwargs=strategy)
    def run(kwargs: dict) -> None:
        stats["execs"] += 1
        try:
            with call_timeout(per_example):
                check(**kwargs)
        except Exception as exc:
            if stats["first_fail"] is None:
                stats["first_fail"] = stats["execs"]
            captured["kwargs"] = kwargs
            captured["exc"] = exc
            raise

    try:
        run()
    except Exception:
        pass

    if not captured:
        return HuntResult(
            target=target_spec,
            status="clean",
            property=plan.name,
            seed=seed_value,
            executions=stats["execs"],
        )

    kwargs = captured["kwargs"]
    exc = captured["exc"]
    is_property = type(exc).__name__ == "PropertyViolation"
    failure = Failure(
        kind="property" if is_property else "crash",
        property=plan.name,
        exception_type=None if is_property else type(exc).__name__,
        message=str(exc),
        args=_reprable(kwargs),
        args_repr=_args_repr(getattr(func, "__name__", "f"), kwargs),
        input_size=_kwargs_size(kwargs),
        location=_location(exc),
    )
    first_fail = stats["first_fail"] or stats["execs"]
    return HuntResult(
        target=target_spec,
        status="failing",
        property=plan.name,
        partner=plan.partner,
        seed=seed_value,
        executions=stats["execs"],
        executions_to_first_failure=first_fail,
        shrink_executions=max(0, stats["execs"] - first_fail),
        failure=failure,
    )


def _reprable(kwargs: dict) -> dict:
    out = {}
    for name, value in kwargs.items():
        if isinstance(value, (int, float, str, bytes, bool, type(None), list, dict, tuple)):
            out[name] = value
        else:
            out[name] = repr(value)
    return out


def _hunt_worker(spec: dict) -> HuntResult:
    func = reload_from_origin(spec["origin_kind"], spec["origin_ref"], spec["qualname"])
    plans = [PropertyPlan(**p) for p in spec["plans"]]
    last_clean: HuntResult | None = None
    for plan in plans:
        partner = None
        if plan.partner:
            partner = reload_from_origin(spec["origin_kind"], spec["origin_ref"], plan.partner)
        result = _run_property(
            func,
            plan,
            partner,
            spec["target"],
            spec["seed"],
            spec["max_examples"],
            spec["per_example"],
        )
        if result.status == "failing":
            return result
        last_clean = result
    if last_clean is not None:
        return last_clean
    return HuntResult(target=spec["target"], status="clean", seed=spec["seed"])


def hunt(
    spec: str,
    *,
    seed: int = 0,
    max_examples: int = 200,
    per_example: float = 2.0,
    plans: list[PropertyPlan] | None = None,
    isolate: bool = True,
    wall_s: float = 30.0,
    mem_mb: int = 2048,
    cpu_s: int = 12,
) -> HuntResult:
    target = load_target(spec)
    if plans is None:
        plans = choose_properties(target, sibling_functions(target))
    worker_spec = {
        "origin_kind": target.origin.kind,
        "origin_ref": target.origin.ref,
        "qualname": target.qualname,
        "target": spec,
        "seed": seed,
        "max_examples": max_examples,
        "per_example": per_example,
        "plans": [p.model_dump() for p in plans],
    }
    if not isolate:
        return _hunt_worker(worker_spec)
    outcome = run_in_subprocess(_hunt_worker, (worker_spec,), wall_s=wall_s, mem_mb=mem_mb, cpu_s=cpu_s)
    if outcome.status == "ok" and isinstance(outcome.value, HuntResult):
        return outcome.value
    if outcome.status == "crash":
        signal_note = f"signal {outcome.signal}" if outcome.signal else f"exit {outcome.exitcode}"
        return HuntResult(
            target=spec,
            status="error",
            message=f"the target crashed the interpreter ({signal_note}) — likely a native-level fault",
        )
    if outcome.status == "timeout":
        return HuntResult(target=spec, status="error", message=f"hunt exceeded {wall_s:g}s wall clock")
    return HuntResult(target=spec, status="error", message=outcome.exc_msg or "hunt failed to run")
