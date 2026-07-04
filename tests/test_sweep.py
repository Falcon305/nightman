from __future__ import annotations

from nightman import server
from nightman.discover import discover
from nightman.sweep import sweep

LIB = """
def first(xs: list[int]) -> int:
    return xs[0]


def safe_first(xs: list[int]) -> int:
    return xs[0] if xs else -1


def divide(a: int, b: int) -> float:
    return a / b


def skipped(xs: list[int]) -> int:  # nightman: ignore
    return xs[0]


def _private(xs: list[int]) -> int:
    return xs[0]
"""


def _pkg(tmp_path):
    (tmp_path / "lib.py").write_text(LIB)
    (tmp_path / "test_lib.py").write_text("def test_x():\n    assert True\n")
    return str(tmp_path)


def test_discover_public_only(tmp_path):
    specs = discover(_pkg(tmp_path))
    names = sorted(s.rsplit(":", 1)[-1] for s in specs)
    assert names == ["divide", "first", "safe_first"]


def test_sweep_ranks_and_grades(tmp_path):
    report = sweep(_pkg(tmp_path), seed=1, max_examples=150, workers=2)
    assert report.scanned == 3
    broken = {r.target.rsplit(":", 1)[-1] for r in report.findings}
    assert "first" in broken and "divide" in broken
    assert "safe_first" not in broken
    assert report.grade in {"D", "F"}
    assert report.findings[0].failure.severity >= report.findings[-1].failure.severity


def test_scan_tool(tmp_path):
    report = server.nightman_scan(_pkg(tmp_path), seed=1, max_examples=150)
    assert report.scanned == 3
    assert len(report.findings) >= 2
    assert "THE NIGHTMAN" in report.report or "broke" in report.report
