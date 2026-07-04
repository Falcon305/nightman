from __future__ import annotations

import asyncio

from nightman.emit import _dotted_module, _render, render_regression_test
from nightman.hunt import hunt

MOD = """
def to_list(n: int) -> list:
    return "not a list"


async def afetch(url: str) -> str:
    raise RuntimeError("boom")


def gen(n: int):
    yield 1 // n


def ponly(a, b, /, c=0):
    return a[b]


class Calc:
    def add(self, a: int, b: int) -> int:
        return a + b
"""


def _module(tmp_path) -> str:
    path = tmp_path / "cases.py"
    path.write_text(MOD)
    return str(path)


def _hunt(tmp_path, func):
    return hunt(f"{_module(tmp_path)}:{func}", seed=1, max_examples=200, isolate=False)


def test_generator_body_is_exercised(tmp_path):
    result = _hunt(tmp_path, "gen")
    assert result.status == "failing"
    assert result.failure.exception_type == "ZeroDivisionError"


def test_async_body_is_exercised(tmp_path):
    result = _hunt(tmp_path, "afetch")
    assert result.status == "failing"
    assert "boom" in result.failure.message


def test_positional_only_calls_without_convention_error(tmp_path):
    result = _hunt(tmp_path, "ponly")
    assert result.status == "failing"
    assert "positional-only" not in result.failure.message


def test_method_target_errors_cleanly(tmp_path):
    result = _hunt(tmp_path, "Calc.add")
    assert result.status == "error"
    assert "method" in result.message


def test_render_handles_nan_and_inf():
    assert _render(float("nan")) == "float('nan')"
    assert _render(float("inf")) == "float('inf')"
    assert _render(-float("inf")) == "float('-inf')"
    assert _render([1.5, float("nan")]) == "[1.5, float('nan')]"


def test_type_contract_test_asserts_the_property(tmp_path):
    result = _hunt(tmp_path, "to_list")
    assert result.status == "failing"
    source = render_regression_test(result)
    assert "isinstance(to_list(**kwargs), list)" in source
    compile(source, "generated", "exec")


def test_dotted_module_walks_package_init(tmp_path):
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "util.py").write_text("def f(x: int) -> int:\n    return x\n")
    module, func = _dotted_module(f"{pkg / 'util.py'}:f")
    assert module == "mypkg.util"
    assert func == "f"


def test_server_advertises_instructions_and_annotations():
    from nightman.server import mcp

    assert mcp.instructions
    tools = asyncio.run(mcp.list_tools())
    by_name = {t.name: t for t in tools}
    assert all(t.title for t in tools)
    assert by_name["nightman_hunt"].annotations.readOnlyHint is True
    assert by_name["nightman_write_regression_test"].annotations.readOnlyHint is False
