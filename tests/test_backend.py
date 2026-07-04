from __future__ import annotations

import pytest

from nightman import hunt as hunt_module
from nightman.hunt import hunt

NARROW = """
def narrow(x: int) -> int:
    if x == 4823:
        raise ValueError("gotcha")
    return x
"""


def _module(tmp_path) -> str:
    path = tmp_path / "n.py"
    path.write_text(NARROW)
    return str(path)


def test_missing_crosshair_degrades_gracefully(tmp_path, monkeypatch):
    monkeypatch.setattr(hunt_module, "_crosshair_available", lambda: False)
    result = hunt(f"{_module(tmp_path)}:narrow", seed=1, max_examples=50, backend="crosshair")
    assert result.status == "error"
    assert "crosshair" in result.message


def test_random_backend_misses_the_narrow_branch(tmp_path):
    result = hunt(f"{_module(tmp_path)}:narrow", seed=1, max_examples=200, backend="random", isolate=False)
    assert result.status == "clean"


def test_crosshair_cracks_the_narrow_branch(tmp_path):
    pytest.importorskip("hypothesis_crosshair_provider")
    result = hunt(f"{_module(tmp_path)}:narrow", seed=1, max_examples=100, backend="crosshair", isolate=False)
    assert result.status == "failing"
    assert result.failure.args == {"x": 4823}
    assert result.failure.verified is True
