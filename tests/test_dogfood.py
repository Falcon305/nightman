from __future__ import annotations

import os

from nightman.hunt import hunt
from nightman.sandbox import _scratch_cwd, _silence_output
from nightman.score import score
from nightman.sweep import sweep
from nightman.target import load_target


def _package(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "models.py").write_text("BONUS = 10\n")
    (pkg / "uses.py").write_text(
        "from .models import BONUS\n\n\ndef add_bonus(n: int) -> int:\n    return n + BONUS\n"
    )
    (pkg / "broken.py").write_text(
        "from .nothing_here import MISSING\n\n\ndef never(x: int) -> int:\n    return x\n"
    )
    return pkg


def test_package_relative_import_loads(tmp_path):
    pkg = _package(tmp_path)
    target = load_target(f"{pkg / 'uses.py'}:add_bonus")
    assert target.func(5) == 15


def test_hunt_on_packaged_module_does_not_crash(tmp_path):
    pkg = _package(tmp_path)
    result = hunt(f"{pkg / 'uses.py'}:add_bonus", seed=1, max_examples=80, isolate=False)
    assert result.status in ("clean", "failing")


def test_scan_survives_an_unimportable_module(tmp_path):
    pkg = _package(tmp_path)
    report = sweep(str(pkg), seed=1, max_examples=60, mode="plain")
    assert report.scanned >= 2
    assert report.errors >= 1
    assert any(r.status == "error" for r in report.findings) or report.errors >= 1


def test_hunt_bad_target_returns_error_not_raise(tmp_path):
    result = hunt(f"{tmp_path / 'nope.py'}:missing", seed=1, max_examples=10)
    assert result.status == "error"
    assert "could not load" in result.message


def test_score_bad_target_returns_clean_report(tmp_path):
    result = score(f"{tmp_path / 'nope.py'}:missing", seed=1, max_examples=10)
    assert result.total == 0
    assert "could not load" in result.report


def test_sandbox_runs_in_disposable_scratch_cwd():
    origin = os.getcwd()
    with _scratch_cwd():
        inside = os.getcwd()
        assert inside != origin
        with open("side_effect.txt", "w") as handle:
            handle.write("x")
    assert os.getcwd() == origin
    assert not os.path.exists(os.path.join(inside, "side_effect.txt"))


def test_sandbox_silences_target_output(capfd):
    with _silence_output():
        os.write(1, b"STDOUT_LEAK")
        os.write(2, b"STDERR_LEAK")
    captured = capfd.readouterr()
    assert "STDOUT_LEAK" not in captured.out
    assert "STDERR_LEAK" not in captured.err
    os.write(1, b"after_restore")
    assert "after_restore" in capfd.readouterr().out
