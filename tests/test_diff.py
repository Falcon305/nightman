from __future__ import annotations

import subprocess

import pytest

from nightman.annotate import to_github
from nightman.diff import filter_to_diff
from nightman.discover import discover
from nightman.sweep import sweep

SHARED = """
def _helper(xs):
    return xs[0]


def alpha(xs: list) -> int:
    return _helper(xs)


def beta(xs: list) -> int:
    return _helper(xs)
"""


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _repo(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t.co")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "lib.py").write_text("def stable(x: int) -> int:\n    return x + 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "base")
    _git(tmp_path, "branch", "-M", "main")
    _git(tmp_path, "checkout", "-b", "feature")
    (tmp_path / "lib.py").write_text(
        "def stable(x: int) -> int:\n    return x + 1\n\n\ndef risky(xs: list) -> int:\n    return xs[0]\n"
    )
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "add risky")


def test_diff_narrows_to_changed_functions(tmp_path):
    _repo(tmp_path)
    specs = discover(str(tmp_path))
    kept = filter_to_diff(specs, str(tmp_path), "main")
    assert kept is not None
    names = {s.rsplit(":", 1)[-1] for s in kept}
    assert names == {"risky"}


def test_diff_returns_none_outside_git(tmp_path):
    (tmp_path / "m.py").write_text("def f(x: int) -> int:\n    return x\n")
    assert filter_to_diff(discover(str(tmp_path)), str(tmp_path), "main") is None


def test_dedup_collapses_shared_crash_site(tmp_path):
    (tmp_path / "mod.py").write_text(SHARED)
    report = sweep(str(tmp_path), seed=1, max_examples=150, mode="plain")
    assert len(report.findings) == 1
    assert report.deduped == 1


def test_github_annotations_are_well_formed(tmp_path):
    (tmp_path / "mod.py").write_text(SHARED)
    report = sweep(str(tmp_path), seed=1, max_examples=150, mode="plain")
    annotation = to_github(report.findings)
    assert annotation.startswith("::error ")
    assert "file=" in annotation and "line=" in annotation and "title=" in annotation


@pytest.mark.parametrize("count", [12])
def test_github_caps_annotation_volume(tmp_path, count):
    from nightman.models import Failure, HuntResult, Location

    findings = [
        HuntResult(
            target=f"m.py:f{i}",
            status="failing",
            property="never-raises",
            failure=Failure(
                kind="crash",
                property="never-raises",
                exception_type="ValueError",
                args={"x": i},
                args_repr=f"f{i}(x={i})",
                input_size=1,
                location=Location(file="m.py", line=i + 1),
            ),
        )
        for i in range(count)
    ]
    annotation = to_github(findings)
    assert annotation.count("::error ") == 10
    assert "::warning::" in annotation
