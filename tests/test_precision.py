from __future__ import annotations

from nightman.config import Config, load_config
from nightman.explain import explain
from nightman.hunt import hunt
from nightman.severity import classify, rank

MOD = """
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


def biggest(xs: list[int]) -> int:
    return max(xs)
"""


def _module(tmp_path) -> str:
    path = tmp_path / "m.py"
    path.write_text(MOD)
    return str(path)


def test_classify_crash_and_property():
    cat, sev, conf = classify("crash", "never-raises", "IndexError", verified=True)
    assert cat == "boundary" and sev == 4 and conf == "verified"
    cat, sev, conf = classify("crash", "never-raises", "ValueError", verified=True)
    assert conf == "heuristic" and sev == 2
    cat, sev, conf = classify("property", "differential", None, verified=False)
    assert cat == "wrong-result" and conf == "high"
    assert rank(4, "verified") > rank(4, "heuristic")


def test_failure_is_classified_and_verified(tmp_path):
    result = hunt(f"{_module(tmp_path)}:search", seed=1, max_examples=400, isolate=False)
    assert result.status == "failing"
    assert result.failure.category == "boundary"
    assert result.failure.severity >= 4
    assert result.failure.verified is True
    assert result.failure.fix_hint


def test_explain_produces_narrative(tmp_path):
    explanation = explain(f"{_module(tmp_path)}:search", seed=1, max_examples=400)
    assert explanation.found
    assert explanation.category == "boundary"
    assert "Fix:" in explanation.report


def test_config_allowlist_suppresses(tmp_path):
    target = f"{_module(tmp_path)}:biggest"
    bare = hunt(target, seed=1, max_examples=300, isolate=False)
    assert bare.status == "failing"
    assert bare.failure.exception_type == "ValueError"
    allowed = hunt(
        target, seed=1, max_examples=300, isolate=False, config=Config(allow={"biggest": ["ValueError"]})
    )
    assert allowed.status == "clean"


def test_config_loads_from_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.nightman]\nexclude = ["vendor/**"]\nmin_confidence = "high"\n'
        '[tool.nightman.allow]\nparse = ["ValueError"]\n'
    )
    config = load_config(str(tmp_path))
    assert "vendor/**" in config.exclude
    assert config.min_confidence == "high"
    assert config.allowed_for("parse") == ["ValueError"]
    assert config.meets_confidence("verified")
    assert not config.meets_confidence("heuristic")
