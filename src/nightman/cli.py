from __future__ import annotations

import argparse
import json
import sys

from .hunt import hunt
from .models import HuntResult
from .persona import render_hunt


def _run_hunt(args: argparse.Namespace) -> HuntResult:
    return hunt(
        args.target,
        seed=args.seed,
        max_examples=args.examples,
        isolate=not args.no_isolate,
    )


def _cmd_hunt(args: argparse.Namespace) -> int:
    result = _run_hunt(args)
    if args.json:
        print(json.dumps(result.model_dump(), indent=2, default=str))
        return 1 if result.status == "failing" else 0
    mode = "plain" if args.plain else "nightman"
    print(render_hunt(result, mode))
    return 1 if result.status == "failing" else 0


def _cmd_harden(args: argparse.Namespace) -> int:
    from .emit import write_regression_test

    result = _run_hunt(args)
    mode = "plain" if args.plain else "nightman"
    print(render_hunt(result, mode))
    if result.status == "failing" and args.write:
        path = write_regression_test(result, root=args.root)
        print(f"\nPinned it in {path}")
    return 1 if result.status == "failing" else 0


def _diff_base(args: argparse.Namespace) -> str | None:
    return args.base if getattr(args, "diff", False) else None


def _cmd_scan(args: argparse.Namespace) -> int:
    from .sweep import sweep

    mode = "plain" if args.plain else "nightman"
    report = sweep(
        args.path,
        seed=args.seed,
        max_examples=args.examples,
        workers=args.workers,
        mode=mode,
        diff_base=_diff_base(args),
    )
    if args.format == "github":
        from .annotate import to_github

        annotations = to_github(report.findings)
        if annotations:
            print(annotations)
    elif args.json:
        print(json.dumps(report.model_dump(), indent=2, default=str))
    else:
        print(report.report)
    return 1 if report.findings else 0


def _cmd_gate(args: argparse.Namespace) -> int:
    from .baseline import filter_new, load_baseline
    from .sweep import sweep

    report = sweep(
        args.path,
        seed=args.seed,
        max_examples=args.examples,
        workers=args.workers,
        mode="plain",
        diff_base=_diff_base(args),
    )
    findings = report.findings
    if args.baseline:
        findings = filter_new(findings, load_baseline(args.path))
    blocking = [r for r in findings if r.failure and r.failure.severity >= args.severity]
    if blocking:
        if args.format == "github":
            from .annotate import to_github

            print(to_github(blocking))
            return 1
        scope = "new " if args.baseline else ""
        print(f"Nightman: {len(blocking)} {scope}blocking finding(s) — he got in.")
        for result in blocking:
            failure = result.failure
            if failure is None:
                continue
            print(f"  [{failure.severity}] {result.target.rsplit(':', 1)[-1]}  {failure.args_repr}")
        return 1
    print("Nightman: nothing new got in. Dayman holds the line.")
    return 0


def _cmd_baseline(args: argparse.Namespace) -> int:
    from .baseline import write_baseline
    from .sweep import sweep

    report = sweep(args.path, seed=args.seed, max_examples=args.examples, workers=args.workers, mode="plain")
    count = write_baseline(args.path, report.findings)
    print(f"Nightman: wrote baseline with {count} known finding(s).")
    return 0


def _cmd_sarif(args: argparse.Namespace) -> int:
    from .sarif import to_sarif
    from .sweep import sweep

    report = sweep(args.path, seed=args.seed, max_examples=args.examples, workers=args.workers, mode="plain")
    payload = json.dumps(to_sarif(report.findings), indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload)
        print(f"Nightman: wrote {len(report.findings)} finding(s) to {args.output}")
    else:
        print(payload)
    return 0


def _cmd_explain(args: argparse.Namespace) -> int:
    from .explain import explain

    explanation = explain(args.target, seed=args.seed, max_examples=args.examples)
    print(explanation.report)
    return 1 if explanation.found else 0


def _cmd_score(args: argparse.Namespace) -> int:
    from .score import score

    result = score(args.target, seed=args.seed, max_examples=args.examples)
    if args.json:
        print(json.dumps(result.model_dump(), indent=2, default=str))
    else:
        print(result.report)
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import logging

    from .server import mcp

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    mcp.run(transport="streamable-http" if args.http else "stdio")
    return 0


def _add_hunt_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target", help="module:function or path/to/file.py:function")
    parser.add_argument("--seed", type=int, default=0, help="RNG seed for reproducibility.")
    parser.add_argument("--examples", type=int, default=300, help="Max candidate inputs to try.")
    parser.add_argument("--plain", action="store_true", help="Flavor-free output.")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    parser.add_argument("--no-isolate", action="store_true", help="Run in-process (no sandbox subprocess).")


def _add_scan_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", nargs="?", default=".", help="File, directory, or package to scan.")
    parser.add_argument("--seed", type=int, default=0, help="RNG seed for reproducibility.")
    parser.add_argument("--examples", type=int, default=200, help="Max candidate inputs per function.")
    parser.add_argument("--workers", type=int, default=4, help="How many functions to hunt in parallel.")
    parser.add_argument("--diff", action="store_true", help="Only hunt functions changed vs the base branch.")
    parser.add_argument("--base", default="origin/main", help="Base git ref for --diff (default origin/main).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nightman", description="The Nightman comes for your untested code.")
    sub = parser.add_subparsers(dest="command", required=True)

    hunt_cmd = sub.add_parser("hunt", help="Hunt for a crashing or property-violating input.")
    _add_hunt_args(hunt_cmd)
    hunt_cmd.set_defaults(func=_cmd_hunt)

    harden = sub.add_parser("harden", help="Hunt, then write the pinned pytest regression test.")
    _add_hunt_args(harden)
    harden.add_argument("--write", action="store_true", help="Write the regression test to disk.")
    harden.add_argument("--root", default=".", help="Repo root to write the test into.")
    harden.set_defaults(func=_cmd_harden)

    explain_cmd = sub.add_parser("explain", help="Hunt a function and explain the failure in plain language.")
    _add_hunt_args(explain_cmd)
    explain_cmd.set_defaults(func=_cmd_explain)

    score_cmd = sub.add_parser("score", help="Mutation-score a function: how many injected bugs Nightman catches.")
    score_cmd.add_argument("target", help="module:function or path/to/file.py:function")
    score_cmd.add_argument("--seed", type=int, default=0, help="RNG seed for reproducibility.")
    score_cmd.add_argument("--examples", type=int, default=150, help="Max inputs tried per mutant.")
    score_cmd.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    score_cmd.set_defaults(func=_cmd_score)

    scan = sub.add_parser("scan", help="Hunt every public function under a path and rank what breaks.")
    _add_scan_args(scan)
    scan.add_argument("--plain", action="store_true", help="Flavor-free output.")
    scan.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    scan.add_argument(
        "--format", choices=("text", "github"), default="text", help="Output format (github = PR annotations)."
    )
    scan.set_defaults(func=_cmd_scan)

    gate = sub.add_parser("gate", help="Scan and fail (exit 1) on findings — for CI.")
    _add_scan_args(gate)
    gate.add_argument("--baseline", action="store_true", help="Only fail on findings not in the baseline.")
    gate.add_argument("--severity", type=int, default=4, help="Minimum severity that blocks (default 4).")
    gate.add_argument(
        "--format", choices=("text", "github"), default="text", help="Output format (github = PR annotations)."
    )
    gate.set_defaults(func=_cmd_gate)

    base = sub.add_parser("baseline", help="Snapshot current findings so only new ones fail later.")
    _add_scan_args(base)
    base.set_defaults(func=_cmd_baseline)

    sarif_cmd = sub.add_parser("sarif", help="Emit SARIF 2.1.0 for GitHub code scanning.")
    _add_scan_args(sarif_cmd)
    sarif_cmd.add_argument("-o", "--output", help="Write SARIF to this file instead of stdout.")
    sarif_cmd.set_defaults(func=_cmd_sarif)

    serve = sub.add_parser("serve", help="Run the MCP server.")
    serve.add_argument("--http", action="store_true", help="Serve over streamable-http instead of stdio.")
    serve.set_defaults(func=_cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
