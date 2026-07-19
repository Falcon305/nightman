from __future__ import annotations

import inspect
from typing import Any

from hypothesis import HealthCheck, given, seed, settings

from .infer import kwargs_strategy
from .models import MutationScore
from .mutate import mutants
from .properties import _invoker
from .target import load_target

_MAX_MUTANTS = 60


def _read(path: str | None) -> str:
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            return handle.read()
    except OSError:
        return ""


def _load_from_source(source: str, func_name: str, origin: str) -> Any:
    namespace: dict[str, Any] = {}
    exec(compile(source, origin, "exec"), namespace)
    return namespace.get(func_name)


def _outcome(call: Any, kwargs: dict) -> str:
    try:
        return repr(("value", call(kwargs)))
    except Exception as exc:
        return repr(("raised", type(exc).__name__))


def _distinguishes(original: Any, mutant: Any, strategy: Any, seed_value: int, max_examples: int) -> bool:
    hit = {"found": False}

    @seed(seed_value)
    @settings(
        max_examples=max_examples,
        database=None,
        deadline=None,
        suppress_health_check=list(HealthCheck),
    )
    @given(kwargs=strategy)
    def run(kwargs: dict) -> None:
        if _outcome(original, kwargs) != _outcome(mutant, kwargs):
            hit["found"] = True
            raise AssertionError

    try:
        run()
    except Exception:
        pass
    return hit["found"]


def _render(target: str, total: int, killed: int, survivors: list[str]) -> str:
    if total == 0:
        return f"Nightman: {target} has no mutable logic to score."
    percent = round(100 * killed / total)
    head = f"🌙 Mutation score for {target}: {percent}% — Nightman caught {killed} of {total} injected mutations."
    if not survivors:
        return head + "\n   Every mutation was noticed. This function is well covered."
    shown = survivors[:10]
    lines = [head, "   Survivors (behaviour Nightman could not distinguish):"]
    lines.extend(f"     - {item}" for item in shown)
    if len(survivors) > len(shown):
        lines.append(f"     … and {len(survivors) - len(shown)} more.")
    return "\n".join(lines)


def score(target: str, *, seed: int = 0, max_examples: int = 150) -> MutationScore:
    try:
        loaded = load_target(target)
    except Exception as exc:
        return MutationScore(
            target=target,
            total=0,
            killed=0,
            survived=0,
            score=1.0,
            report=f"Nightman: could not load {target} to score it — {exc}",
        )
    func_name = loaded.qualname.split(".")[-1]
    source = _read(inspect.getsourcefile(loaded.func))
    original = _load_from_source(source, func_name, "<original>") if source else None
    if original is None:
        return MutationScore(
            target=target,
            total=0,
            killed=0,
            survived=0,
            score=1.0,
            report=f"Nightman: could not read the source of {target} to mutate it.",
        )
    strategy = kwargs_strategy(original)
    original_call = _invoker(original)
    killed = 0
    survivors: list[str] = []
    total = 0
    for mutant in mutants(source, func_name)[:_MAX_MUTANTS]:
        try:
            mutant_func = _load_from_source(mutant.source, func_name, "<mutant>")
        except Exception:
            continue
        if mutant_func is None:
            continue
        total += 1
        if _distinguishes(original_call, _invoker(mutant_func), strategy, seed, max_examples):
            killed += 1
        else:
            survivors.append(f"line {mutant.line}: {mutant.description}")
    return MutationScore(
        target=target,
        total=total,
        killed=killed,
        survived=len(survivors),
        score=killed / total if total else 1.0,
        survivors=survivors,
        report=_render(target, total, killed, survivors),
    )
