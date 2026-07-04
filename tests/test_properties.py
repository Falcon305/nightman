from __future__ import annotations

from nightman.hunt import hunt

MOD = """
def add_mod(a: int, b: int) -> int:
    return (a - b) % 7


def real_add(a: int, b: int) -> int:
    return a + b


def maximum(xs: list[int]) -> int:
    return xs[0] if xs else 0


def total(xs: list[int]) -> int:
    return sum(xs)


def to_tags(s: str) -> list[str]:
    return s.split(",") if s else None


def good_tags(s: str) -> list[str]:
    return s.split(",")
"""


def _module(tmp_path) -> str:
    path = tmp_path / "p.py"
    path.write_text(MOD)
    return str(path)


def _hunt(tmp_path, func):
    return hunt(f"{_module(tmp_path)}:{func}", seed=2, max_examples=300, isolate=False)


def test_commutativity_violation_detected(tmp_path):
    result = _hunt(tmp_path, "add_mod")
    assert result.status == "failing"
    assert result.property == "commutative"


def test_real_commutative_stays_clean(tmp_path):
    assert _hunt(tmp_path, "real_add").status == "clean"


def test_permutation_violation_detected(tmp_path):
    result = _hunt(tmp_path, "maximum")
    assert result.status == "failing"
    assert result.property == "permutation"


def test_order_free_function_stays_clean(tmp_path):
    assert _hunt(tmp_path, "total").status == "clean"


def test_type_contract_violation_detected(tmp_path):
    result = _hunt(tmp_path, "to_tags")
    assert result.status == "failing"
    assert result.property == "type-contract"


def test_type_contract_stays_clean(tmp_path):
    assert _hunt(tmp_path, "good_tags").status == "clean"
