<div align="center">

<img src="./assets/nightman-cometh.webp" alt="Charlie performing Dayman in 'The Nightman Cometh'" width="620" />

# Nightman

**The Nightman comes for your untested code.**

Point it at a Python function. It throws adversarial inputs until something breaks, shrinks the failure to its smallest form, and hands you the pytest regression test that proves it. A **bug-finder, not a test-writer** — it only writes a test once it already has a crash in hand.

Ships as a **CLI** and an **MCP server**. Second in a gang of *It's Always Sunny*-flavored dev tools, after [Charlie Work](https://github.com/Falcon305/charlie-work-mcp).

</div>

---

> **🌙 THE NIGHTMAN COMETH.** *Sneaky and mean. A master of karate — and of the empty list you forgot to handle.*

The jokes are a **toggle, not a tax** — pass `--plain` (or set `NIGHTMAN_VOICE=off`) and every line comes back flavor-free, paste-into-a-ticket clean. CI and machine output are always plain.

## Why not just "AI writes my tests"?

Because auto-generated tests are distrusted for good reasons — they pin whatever the code already does, they flake, they assert nothing that matters. Nightman is the opposite by construction:

- **It leads with a real failure.** Nothing is written until a generated input actually crashes the function or violates a stated property. No crash, no test.
- **What it commits can't flake.** The deliverable is a *frozen, minimized* `pytest.param(...)` case — one pinned input, deterministic, no live fuzzer in your CI.
- **You write zero properties.** Nightman infers them from type hints, signatures, and docstrings — killing the #1 reason people bounce off property-based testing.

## Quickstart

Run it straight from the repo with [`uv`](https://docs.astral.sh/uv/) — no clone, no build:

```bash
uvx --from git+https://github.com/Falcon305/nightman nightman hunt yourmodule:your_function
```

Or point it at a file directly:

```bash
uvx --from git+https://github.com/Falcon305/nightman nightman hunt path/to/parsing.py:parse
```

## Scan a whole codebase

Don't want to name functions one at a time? Point Nightman at a file, directory, or package and he hunts *every* public function, then ranks what breaks worst-first:

```
$ nightman scan src/

🌙 THE NIGHTMAN CAME FOR 34 FUNCTION(S). He broke 5.
   Grade D. Worst first:
  [5/verified ] parse_config       KeyError            parse_config(cfg={})
  [4/verified ] to_slug            IndexError          to_slug(title='')
  [4/verified ] clamp              ZeroDivisionError   clamp(x=0, lo=0, hi=0)
  [4/high     ] encode_token       UnicodeEncodeError  encode_token(s='\x80')
  [3/heuristic] load_rows          ValueError          load_rows(path='')
```

It loads modules the way Python does — a file inside a package is imported by its dotted path, so `from .models import ...` and other relative imports resolve correctly — and a module it can't import (a syntax error, a missing dependency) is marked as an error and skipped, never crashing the whole scan. Every finding carries a **category, a severity (1–5), and a confidence tier** — `verified` means Nightman replayed the minimal input and it reproduced every time. When several functions crash at the same underlying line, he **collapses them into one finding** so the report stays signal. Tune what he chases with `[tool.nightman]` in `pyproject.toml`: exclude globs, a `min_confidence` floor, and per-function `allow` lists so an *intended* exception is never re-flagged.

## Fail CI only on new crashes

`nightman gate` scans and exits non-zero when something breaks — and with a committed baseline it fails a PR **only on crashes that PR introduced**, never the legacy backlog. On a big repo, `--diff` hunts **only the functions the PR actually touched** (against `git merge-base`), turning a nightly-only scan into a per-PR check that finishes in seconds. Drop the Action into a workflow:

```yaml
- uses: Falcon305/nightman@master
  with:
    path: src/
    severity: "4"
    baseline: "true"
    diff: "true"        # only hunt what this PR changed
```

The Action reports findings as **inline PR annotations** (`--format github`) right on the changed lines. And `nightman sarif -o nightman.sarif` emits SARIF 2.1.0, so findings also show up in GitHub's Security tab via `github/codeql-action/upload-sarif`.

## What it looks like

```
$ nightman hunt binsearch.py:search

🌙 THE NIGHTMAN COMETH.
   He came for search() with:  search(arr=[], target=0)
   → IndexError: list index out of range at binsearch.py:5
   found on try #1.
   shrunk to its smallest form in 310 more.
```

`nightman harden binsearch.py:search --write` does the same, then drops a committable regression test:

```python
# Regression test written by Nightman (github.com/Falcon305/nightman).
# The Nightman came for search() and it broke:
#   search(arr=[], target=0)
#   -> IndexError: list index out of range
# The minimized failing input is pinned below. Delete this test once the bug is dead.
import pytest

from binsearch import search


@pytest.mark.parametrize("kwargs", [pytest.param({'arr': [], 'target': 0}, id='nightman-3821a3')])
def test_search_nightman(kwargs):
    search(**kwargs)
```

That test **fails on the buggy code and passes once you fix it** — a real regression net, not a snapshot of today's behavior.

## How it works (delegate, don't reinvent)

Nightman's value is the orchestration, the sandbox, and the committable artifact — not a new fuzzer. Under the hood it stands on the best open engines:

- **Generation + shrinking → [Hypothesis](https://hypothesis.readthedocs.io/).** Its shrinking engine is world-class; Nightman drives it and captures the minimized counterexample.
- **Strategy inference** from type hints (`from_type`/`builds`), with a fallback ladder for untyped code: docstring types → default values → parameter-name heuristics → a hand-built **chaos corpus** (empty collections, `NaN`/±inf, boundary ints, surrogate/`\x00`/huge strings).
- **Properties**, strongest-first: a *never-crashes* floor, plus `roundtrip` (`decode(encode(x)) == x`, detected by name pairs), `idempotence`, `commutativity` and `permutation`-invariance (metamorphic, name-gated so they never cry wolf), a `type-contract` check (does the return match its annotation?), and a **differential** oracle for comparing a suspect against a reference.
- **A sandboxed executor** — each hunt runs in a spawned subprocess with CPU/memory limits, so a memory bomb or an infinite loop is capped, and a native **segfault survives as a reported result instead of taking down the run**. The child runs in a throwaway working directory with its stdout/stderr muted, so fuzzing a function that writes files or prints never litters your repo or floods the terminal, and child processes are always reaped so a repo-wide scan can't leak a runaway interpreter.
- **A symbolic backend for the narrow branches** — random search will never guess `if x == 4823`. Install the extra (`pip install nightman[crosshair]`) and add `--backend crosshair` to hunt with [CrossHair](https://github.com/pschanely/crosshair)'s SMT solver, which reasons its way to exact-constant and narrow-branch bugs. Solver-found inputs are always re-verified against the real function, so a hallucinated example never becomes a false alarm.
- **Handles the awkward shapes** — `async def` functions are awaited, generators are drained, and positional-only parameters are called correctly, so the body actually runs instead of a coroutine or generator object slipping through untested.

Every emitted regression test is pinned to the Nightman and seed that found it, and renders exotic inputs faithfully — `float('nan')`, `float('inf')`, and nested containers round-trip to valid, importable Python.

## Proving it works — the eval

Novelty isn't the moat (Anthropic and AWS have both shown agents can do this); a *trustworthy, packaged* tool is. So Nightman ships a reproducible, seeded eval over a corpus of **planted bugs** — off-by-one, empty-input, unicode, unsafe `eval`, integer truncation, runaway recursion, and more. For each it measures detection, repro minimality, and time-to-first-failure — and critically, **runs the same hunt against the *fixed* code and requires zero false positives** (the first thing a skeptic checks).

```
$ python evals/run.py
Nightman eval — 10 planted bugs, 4 seeds each

category             oracle        detect  trials  min|canon  ttff   fp
-----------------------------------------------------------------------
boundary_index       crash         yes     4/4     0|0        1      -
comparison_flip      differential  yes     4/4     3|2        7      -
empty_input          crash         yes     4/4     0|0        1      -
integer_truncation   differential  yes     4/4     4|2        3      -
off_by_one           crash         yes     4/4     1|1        1      -
off_by_one           differential  yes     4/4     2|2        1      -
recursion            crash         yes     4/4     6|1        2      -
type_coercion        crash         yes     4/4     1|1        1      -
unicode_edge         crash         yes     4/4     1|1        2      -
unsafe_eval          crash         yes     4/4     0|0        1      -

detection_rate      : 100%  (10/10)
false_positive_rate : 0%   (must be 0%)
median minimal input: 1.0
median TTFF (execs) : 1.0
RESULT: PASS
```

Every planted bug found, every one shrunk to a near-minimal input, and **not one false alarm on the fixed code**.

## Are the generated tests actually any good?

A regression test is only worth committing if it would *catch a regression*. `nightman score` proves it does — it injects standard mutations into your function (flipped operators, off-by-one constants, swapped comparisons) and reports the fraction Nightman catches by finding an input that tells the mutant apart from the original:

```
$ nightman score src/pricing.py:total

🌙 Mutation score for src/pricing.py:total: 92% — Nightman caught 11 of 12 injected mutations.
   Survivors (behaviour Nightman could not distinguish):
     - line 7: integer 0 to 1
```

A high score means a Nightman-written test would notice if someone broke the logic; a survivor points at behaviour that isn't pinned down yet. Writing this feature is also how Nightman got sharper — the scorer caught that the input generator was under-sampling small boundaries like `1` and `2`, so those are now probed on every typed `int` and `float`, and off-by-one bugs surface more reliably.

## For your coding agent (MCP)

Nightman is also an MCP server, so an agent can hunt bugs and write regression tests itself. Point Claude Desktop / Cursor / Claude Code at it:

```json
{
  "mcpServers": {
    "nightman": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Falcon305/nightman", "nightman", "serve"]
    }
  }
}
```

It exposes seven structured-output tools — `nightman_infer_inputs`, `nightman_hunt`, `nightman_harden`, `nightman_write_regression_test`, `nightman_explain` (root-cause + severity), `nightman_scan` (whole-repo sweep), and `nightman_score` (mutation score) — plus a `harden_function` prompt that scripts the whole loop. Each tool carries a human-readable title and behavioral annotations (the five read-only tools are marked `readOnlyHint`, so a well-behaved client won't nag for confirmation), and the server ships workflow `instructions` that teach an agent to chain hunt → explain → write-test and to respect allow-lists. Then: *"Harden `parse` in parser.py — find how it breaks, fix it, and leave a regression test."*

## Development

```bash
uv sync --extra dev
uv run ruff check . && uv run mypy && uv run pytest -q
uv run python evals/run.py
```

CI runs ruff + mypy (typed) + pytest + the eval across Python 3.11–3.13. Releases publish to PyPI via OIDC Trusted Publishing.

## Roadmap

Where the Nightman is headed next:

- **A persistent example database** — sync Hypothesis's corpus across runs so a known failure reproduces instantly and the seed pool compounds over time.

Already shipped: the CrossHair symbolic backend (`--backend crosshair`), mutation scoring (`nightman score`), `--diff` PR-only hunting, duplicate crash-site collapsing, and inline GitHub PR annotations.

## The gang

Each ships as its own standalone tool: **[Charlie Work](https://github.com/Falcon305/charlie-work-mcp)** (the toil nobody wants to do) · **Nightman** (the input your code wasn't ready for) · more coming.

## License

Code: MIT.

The hero image is a still from *It's Always Sunny in Philadelphia*'s "The Nightman Cometh" (S4E13, © FX Networks), used here for identification and commentary. It is not covered by the MIT license and remains the property of its rights holder. An original vector rendition ships at [`assets/hero.svg`](./assets/hero.svg).
