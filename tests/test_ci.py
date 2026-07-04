from __future__ import annotations

from nightman import cli
from nightman.baseline import filter_new, load_baseline, write_baseline
from nightman.sarif import to_sarif
from nightman.sweep import sweep

LIB = """
def first(xs: list[int]) -> int:
    return xs[0]


def divide(a: int, b: int) -> float:
    return a / b


def safe(xs: list[int]) -> int:
    return xs[0] if xs else 0
"""


def _pkg(tmp_path) -> str:
    (tmp_path / "lib.py").write_text(LIB)
    return str(tmp_path)


def test_baseline_roundtrip_silences_known(tmp_path):
    pkg = _pkg(tmp_path)
    report = sweep(pkg, seed=1, max_examples=150, workers=2)
    written = write_baseline(pkg, report.findings)
    assert written >= 2
    baseline = load_baseline(pkg)
    assert filter_new(report.findings, baseline) == []


def test_gate_exit_codes(tmp_path):
    pkg = _pkg(tmp_path)
    assert cli.main(["gate", pkg, "--seed", "1", "--examples", "150"]) == 1
    assert cli.main(["baseline", pkg, "--seed", "1", "--examples", "150"]) == 0
    assert cli.main(["gate", pkg, "--seed", "1", "--examples", "150", "--baseline"]) == 0


def test_sarif_structure(tmp_path):
    report = sweep(_pkg(tmp_path), seed=1, max_examples=150, workers=2)
    doc = to_sarif(report.findings)
    assert doc["version"] == "2.1.0"
    run = doc["runs"][0]
    assert run["tool"]["driver"]["name"] == "nightman"
    result = run["results"][0]
    assert result["ruleId"].startswith("nightman/")
    assert result["partialFingerprints"]["primaryLocationLineHash"]
    assert result["level"] in {"error", "warning"}
