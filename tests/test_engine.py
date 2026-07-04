from __future__ import annotations

from nightman import server
from nightman.emit import render_regression_test
from nightman.hunt import hunt
from nightman.infer import describe_strategies
from nightman.models import PropertyPlan
from nightman.target import load_target

BUGGY = """
def search(arr: list[int], target: int) -> int:
    lo, hi = 0, len(arr)
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        if arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1


def safe_max(xs: list[int]) -> int:
    return max(xs) if xs else 0


def encode(s: str) -> str:
    return s.replace(",", "\\\\,")


def decode(s: str) -> str:
    return s.replace("\\\\,", ",")


def buggy_avg(xs: list[int]) -> float:
    return sum(xs) // len(xs) if xs else 0.0


def fixed_avg(xs: list[int]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def spins(n: int) -> int:
    while True:
        n += 1
"""


def _module(tmp_path) -> str:
    path = tmp_path / "sample.py"
    path.write_text(BUGGY)
    return str(path)


def test_infer_strategies_reads_type_hints(tmp_path):
    target = load_target(f"{_module(tmp_path)}:search")
    described = describe_strategies(target.func)
    assert "from_type" in described["arr"]
    assert "from_type" in described["target"]


def test_hunt_finds_and_shrinks_crash(tmp_path):
    result = hunt(f"{_module(tmp_path)}:search", seed=1, max_examples=400, isolate=False)
    assert result.status == "failing"
    assert result.failure.exception_type == "IndexError"
    assert result.failure.args["arr"] == []
    assert result.failure.input_size <= 2


def test_hunt_clean_on_correct_function(tmp_path):
    result = hunt(f"{_module(tmp_path)}:safe_max", seed=1, max_examples=300, isolate=False)
    assert result.status == "clean"


def test_roundtrip_clean_when_inverse_holds(tmp_path):
    result = hunt(f"{_module(tmp_path)}:encode", seed=2, max_examples=300, isolate=False)
    assert result.status == "clean"


def test_differential_catches_wrong_value(tmp_path):
    plan = PropertyPlan(name="differential", partner="fixed_avg")
    result = hunt(f"{_module(tmp_path)}:buggy_avg", seed=3, max_examples=400, plans=[plan], isolate=False)
    assert result.status == "failing"
    assert result.property == "differential"
    assert "differs" in result.failure.message


def test_timeout_is_caught(tmp_path):
    result = hunt(f"{_module(tmp_path)}:spins", seed=1, max_examples=25, per_example=0.3, isolate=False)
    assert result.status == "failing"
    assert result.failure.exception_type == "TimeoutError"


def test_isolated_hunt_matches_inprocess(tmp_path):
    result = hunt(f"{_module(tmp_path)}:search", seed=1, max_examples=400, isolate=True)
    assert result.status == "failing"
    assert result.failure.exception_type == "IndexError"


def test_render_regression_test_is_valid_python(tmp_path):
    result = hunt(f"{_module(tmp_path)}:search", seed=1, max_examples=400, isolate=False)
    source = render_regression_test(result)
    assert "def test_search_nightman" in source
    assert "pytest.param" in source
    compile(source, "test_search_nightman.py", "exec")


def test_server_hunt_tool(tmp_path):
    result = server.nightman_hunt(f"{_module(tmp_path)}:search", seed=1)
    assert result.status == "failing"
    infer = server.nightman_infer_inputs(f"{_module(tmp_path)}:search")
    assert any(p.name == "never-raises" for p in infer.properties)
