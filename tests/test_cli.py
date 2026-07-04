from __future__ import annotations

import json

from nightman import cli
from nightman.models import Failure, HuntResult, Location
from nightman.persona import render_hunt

BUGGY = """
def crasher(xs: list[int]) -> int:
    return xs[5]
"""


def _module(tmp_path) -> str:
    path = tmp_path / "mod.py"
    path.write_text(BUGGY)
    return str(path)


def test_cli_hunt_json_exits_one_on_bug(tmp_path, capsys):
    code = cli.main(["hunt", f"{_module(tmp_path)}:crasher", "--seed", "1", "--json", "--no-isolate"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failing"
    assert payload["failure"]["exception_type"] == "IndexError"


def test_cli_harden_writes_test(tmp_path, capsys):
    code = cli.main(
        [
            "harden",
            f"{_module(tmp_path)}:crasher",
            "--seed",
            "1",
            "--plain",
            "--no-isolate",
            "--write",
            "--root",
            str(tmp_path),
        ]
    )
    assert code == 1
    out = capsys.readouterr().out
    assert "Pinned it in" in out
    assert (tmp_path / "tests" / "test_crasher_nightman.py").exists()


def test_persona_clean_and_error():
    clean = HuntResult(target="m.py:f", status="clean", executions=300)
    assert "Dayman" in render_hunt(clean, "nightman")
    assert "PASS" in render_hunt(clean, "plain")
    err = HuntResult(target="m.py:f", status="error", message="native fault")
    assert "native fault" in render_hunt(err, "nightman")


def test_persona_failing_voice():
    failure = Failure(
        kind="crash",
        property="never-raises",
        exception_type="IndexError",
        message="list index out of range",
        args={"xs": []},
        args_repr="crasher(xs=[])",
        input_size=0,
        location=Location(file="mod.py", line=3, func="crasher"),
    )
    result = HuntResult(
        target="mod.py:crasher",
        status="failing",
        property="never-raises",
        executions=42,
        executions_to_first_failure=1,
        shrink_executions=41,
        failure=failure,
    )
    voice = render_hunt(result, "nightman")
    assert "THE NIGHTMAN COMETH" in voice
    assert "mod.py:3" in voice
