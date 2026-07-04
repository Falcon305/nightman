from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .emit import render_regression_test, write_regression_test
from .explain import explain
from .hunt import hunt
from .infer import describe_strategies
from .models import Explanation, HardenResult, HuntResult, InferResult, ScanReport
from .properties import choose_properties
from .sweep import sweep
from .target import load_target, sibling_functions

mcp = FastMCP("nightman")


@mcp.tool()
def nightman_infer_inputs(target: str) -> InferResult:
    """Show how the Nightman will attack a function: the per-argument input strategy
    inferred from its signature, and the properties he will try to break, strongest first.
    Target is module:function or path/to/file.py:function."""
    loaded = load_target(target)
    plans = choose_properties(loaded, sibling_functions(loaded))
    return InferResult(
        target=target,
        strategies=describe_strategies(loaded.func),
        properties=plans,
    )


@mcp.tool()
def nightman_hunt(target: str, seed: int = 0, max_examples: int = 300) -> HuntResult:
    """Hunt for an input that crashes a function or violates an inferred property.
    Returns the minimal failing input (already shrunk) plus the exception and location,
    or a clean verdict. Runs the target in a sandboxed subprocess with resource limits."""
    return hunt(target, seed=seed, max_examples=max_examples)


@mcp.tool()
def nightman_harden(target: str, seed: int = 0, max_examples: int = 300) -> HardenResult:
    """Hunt for a failure and, if one is found, render the pinned pytest regression test
    that reproduces it — without writing to disk. The test fails on the buggy code and
    passes once it is fixed."""
    result = hunt(target, seed=seed, max_examples=max_examples)
    source = render_regression_test(result, partner=result.partner) if result.status == "failing" else None
    return HardenResult(result=result, test_source=source)


@mcp.tool()
def nightman_write_regression_test(
    target: str, root: str = ".", seed: int = 0, max_examples: int = 300
) -> HardenResult:
    """Hunt for a failure and, if one is found, write the pinned pytest regression test into
    the repo's tests/ directory. Returns the path and the test source."""
    result = hunt(target, seed=seed, max_examples=max_examples)
    if result.status != "failing":
        return HardenResult(result=result)
    path = write_regression_test(result, root=root, partner=result.partner)
    source = render_regression_test(result, partner=result.partner)
    return HardenResult(result=result, test_source=source, wrote=path)


@mcp.tool()
def nightman_explain(target: str, seed: int = 0, max_examples: int = 300) -> Explanation:
    """Hunt a function and explain the failure in plain language: the minimal input, the
    exception, a category and severity, whether it was replayed to confirm it reproduces,
    and a concrete fix hint. Use this to understand *why* a function is fragile."""
    return explain(target, seed=seed, max_examples=max_examples)


@mcp.tool()
def nightman_scan(path: str, seed: int = 0, max_examples: int = 200) -> ScanReport:
    """Hunt every public function under a file, directory, or package and return the ones that
    break, ranked worst-first by severity and confidence, with an overall grade. Point this at a
    repo to find the crashes hiding across the whole codebase in one shot."""
    return sweep(path, seed=seed, max_examples=max_examples, mode="plain")


@mcp.prompt()
def harden_function(target: str) -> str:
    """A workflow for hardening a Python function against edge cases with Nightman."""
    return (
        f"Harden the function `{target}` using the Nightman tools.\n"
        f"1. Call nightman_infer_inputs to see the inputs and properties in play.\n"
        f"2. Call nightman_hunt to find a failing input.\n"
        f"3. If it fails, propose a fix to the function, explain the root cause, then call "
        f"nightman_write_regression_test so the bug can never sneak back in.\n"
        f"4. Re-run nightman_hunt to confirm the Nightman finds nothing."
    )
