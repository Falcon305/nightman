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


def _cmd_serve(args: argparse.Namespace) -> int:
    from .server import mcp

    mcp.run(transport="streamable-http" if args.http else "stdio")
    return 0


def _add_hunt_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target", help="module:function or path/to/file.py:function")
    parser.add_argument("--seed", type=int, default=0, help="RNG seed for reproducibility.")
    parser.add_argument("--examples", type=int, default=300, help="Max candidate inputs to try.")
    parser.add_argument("--plain", action="store_true", help="Flavor-free output.")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    parser.add_argument("--no-isolate", action="store_true", help="Run in-process (no sandbox subprocess).")


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
