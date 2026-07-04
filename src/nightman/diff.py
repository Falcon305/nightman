from __future__ import annotations

import ast
import os
import re
import subprocess

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))?")


def _git(root: str, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", root, *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def _repo_root(root: str) -> str | None:
    top = _git(root, "rev-parse", "--show-toplevel")
    return top.strip() if top else None


def _diff_range(root: str, base: str) -> list[str]:
    merged = _git(root, "merge-base", base, "HEAD")
    if merged and merged.strip():
        return [f"{merged.strip()}...HEAD"]
    return []


def _parse_diff(text: str, repo: str) -> dict[str, set[int]]:
    changed: dict[str, set[int]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path == "/dev/null":
                current = None
                continue
            if path.startswith("b/"):
                path = path[2:]
            current = os.path.abspath(os.path.join(repo, path))
            changed.setdefault(current, set())
        elif current is not None:
            match = _HUNK.match(line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2) or 1)
                changed[current].update(range(start, start + max(count, 1)))
    return changed


def changed_lines(root: str, base: str) -> dict[str, set[int]] | None:
    repo = _repo_root(root)
    if repo is None:
        return None
    text = _git(root, "diff", "--unified=0", "--no-color", *_diff_range(root, base))
    if text is None:
        return None
    return _parse_diff(text, repo)


def _function_spans(source: str) -> dict[str, tuple[int, int]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    spans: dict[str, tuple[int, int]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = min([node.lineno, *(d.lineno for d in node.decorator_list)])
            spans[node.name] = (start, node.end_lineno or node.lineno)
    return spans


def filter_to_diff(specs: list[str], root: str, base: str) -> list[str] | None:
    changed = changed_lines(root, base)
    if changed is None:
        return None
    kept: list[str] = []
    cache: dict[str, dict[str, tuple[int, int]]] = {}
    for spec in specs:
        path, func = spec.rsplit(":", 1)
        absolute = os.path.abspath(path)
        touched = changed.get(absolute)
        if not touched:
            continue
        if path not in cache:
            try:
                with open(path, encoding="utf-8", errors="ignore") as handle:
                    cache[path] = _function_spans(handle.read())
            except OSError:
                cache[path] = {}
        span = cache[path].get(func)
        if span and any(span[0] <= line <= span[1] for line in touched):
            kept.append(spec)
    return kept
