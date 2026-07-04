from __future__ import annotations

import ast
import os
from fnmatch import fnmatch

_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "build",
    "dist",
}
_IGNORE = "nightman: ignore"


def _public_functions(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    names = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        decl_line = lines[node.lineno - 1] if 0 <= node.lineno - 1 < len(lines) else ""
        if _IGNORE in decl_line:
            continue
        names.append(node.name)
    return names


def _is_source_file(name: str) -> bool:
    return name.endswith(".py") and not name.startswith("test_") and not name.endswith("_test.py")


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            return handle.read()
    except OSError:
        return ""


def _excluded(rel: str, patterns: list[str]) -> bool:
    return any(fnmatch(rel, pattern) for pattern in patterns)


def discover(path: str, exclude: list[str] | None = None) -> list[str]:
    patterns = exclude or []
    specs: list[str] = []
    if os.path.isfile(path):
        source = _read(path)
        if _IGNORE + "-file" in source:
            return []
        for name in _public_functions(source):
            specs.append(f"{path}:{name}")
        return specs
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for filename in sorted(filenames):
            if not _is_source_file(filename):
                continue
            full = os.path.join(dirpath, filename)
            rel = os.path.relpath(full, path)
            if _excluded(rel, patterns):
                continue
            source = _read(full)
            if _IGNORE + "-file" in source:
                continue
            for name in _public_functions(source):
                specs.append(f"{full}:{name}")
    return sorted(specs)
