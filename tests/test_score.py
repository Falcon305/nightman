from __future__ import annotations

from nightman.mutate import mutants
from nightman.score import score

MOD = """
def price(qty: int, unit: int) -> int:
    return qty * unit + 5


def classify(x: int) -> str:
    if x > 0:
        return "positive"
    if x < 0:
        return "negative"
    return "zero"


def dead(x: int) -> int:
    unused = x + 1
    return x
"""


def _module(tmp_path) -> str:
    path = tmp_path / "m.py"
    path.write_text(MOD)
    return str(path)


def test_mutants_cover_operators_and_constants(tmp_path):
    generated = mutants(MOD, "price")
    kinds = {m.description for m in generated}
    assert any("Mult" in k for k in kinds)
    assert any("Add" in k for k in kinds)
    assert any("integer 5" in k for k in kinds)
    assert all(compile(m.source, "m", "exec") for m in generated)


def test_score_catches_all_mutations_of_a_tight_function(tmp_path):
    result = score(f"{_module(tmp_path)}:price", seed=1, max_examples=120)
    assert result.total >= 3
    assert result.killed == result.total
    assert result.score == 1.0


def test_score_catches_boundary_off_by_one(tmp_path):
    result = score(f"{_module(tmp_path)}:classify", seed=1, max_examples=120)
    assert result.score == 1.0


def test_score_reports_survivors_for_dead_logic(tmp_path):
    result = score(f"{_module(tmp_path)}:dead", seed=1, max_examples=80)
    assert result.total >= 1
    assert result.survived == result.total
    assert result.killed == 0


def test_boundary_augment_samples_small_positive_ints():
    from hypothesis import HealthCheck, given, seed, settings

    from nightman.infer import kwargs_strategy

    def f(x: int) -> int:
        return x

    seen: set[int] = set()

    @seed(1)
    @settings(max_examples=200, database=None, deadline=None, suppress_health_check=list(HealthCheck))
    @given(kwargs=kwargs_strategy(f))
    def run(kwargs: dict) -> None:
        seen.add(kwargs["x"])

    run()
    assert 1 in seen
    assert 2 in seen
