from __future__ import annotations

import json
import os

from .models import HuntResult

_DIR = ".nightman"
_FILE = "baseline.json"


def fingerprint(result: HuntResult) -> str:
    func = result.target.rsplit(":", 1)[-1].split(".")[-1]
    if result.failure is None:
        return f"clean:{func}"
    signal = result.failure.exception_type or result.property
    return f"{result.failure.category}:{func}:{signal}"


def write_baseline(root: str, findings: list[HuntResult]) -> int:
    prints = sorted({fingerprint(r) for r in findings})
    directory = os.path.join(root, _DIR)
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, _FILE), "w", encoding="utf-8") as handle:
        json.dump({"fingerprints": prints}, handle, indent=2)
    return len(prints)


def load_baseline(root: str) -> set[str]:
    path = os.path.join(root, _DIR, _FILE)
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as handle:
        return set(json.load(handle).get("fingerprints", []))


def filter_new(findings: list[HuntResult], baseline: set[str]) -> list[HuntResult]:
    return [r for r in findings if fingerprint(r) not in baseline]
