from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from .config import Config, load_config
from .diff import filter_to_diff
from .discover import discover
from .hunt import hunt
from .models import HuntResult, ScanReport
from .persona import render_scan
from .severity import rank


def _config_root(path: str) -> str:
    return path if os.path.isdir(path) else (os.path.dirname(path) or ".")


def _signature(result: HuntResult) -> tuple:
    failure = result.failure
    assert failure is not None
    location = failure.location
    site = (location.file, location.line) if location else (result.target.rsplit(":", 1)[0], None)
    return (*site, failure.exception_type or result.property)


def _dedup(findings: list[HuntResult]) -> tuple[list[HuntResult], int]:
    seen: set[tuple] = set()
    kept: list[HuntResult] = []
    for result in findings:
        signature = _signature(result)
        if signature in seen:
            continue
        seen.add(signature)
        kept.append(result)
    return kept, len(findings) - len(kept)


def _grade(findings: int, scanned: int) -> str:
    if scanned == 0 or findings == 0:
        return "A"
    ratio = findings / scanned
    if ratio <= 0.05:
        return "B"
    if ratio <= 0.15:
        return "C"
    if ratio <= 0.30:
        return "D"
    return "F"


def _finding_rank(result: HuntResult) -> float:
    if result.failure is None:
        return 0.0
    return rank(result.failure.severity, result.failure.confidence)


def sweep(
    path: str,
    *,
    seed: int = 0,
    max_examples: int = 200,
    config: Config | None = None,
    workers: int = 4,
    wall_s: float = 30.0,
    mode: str = "nightman",
    diff_base: str | None = None,
    backend: str = "random",
) -> ScanReport:
    resolved = config or load_config(_config_root(path))
    specs = discover(path, exclude=resolved.exclude)
    if diff_base:
        narrowed = filter_to_diff(specs, _config_root(path), diff_base)
        if narrowed is not None:
            specs = narrowed
    results: list[HuntResult] = []
    if specs:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = [
                pool.submit(
                    hunt,
                    spec,
                    seed=seed,
                    max_examples=max_examples,
                    config=resolved,
                    wall_s=wall_s,
                    backend=backend,
                )
                for spec in specs
            ]
            results = [future.result() for future in futures]

    findings = [
        r
        for r in results
        if r.status == "failing" and r.failure is not None and resolved.meets_confidence(r.failure.confidence)
    ]
    findings.sort(key=_finding_rank, reverse=True)
    findings, deduped = _dedup(findings)
    clean = sum(1 for r in results if r.status == "clean")
    errors = sum(1 for r in results if r.status == "error")
    counts: dict[str, int] = {}
    for r in findings:
        assert r.failure is not None
        counts[r.failure.confidence] = counts.get(r.failure.confidence, 0) + 1

    report = ScanReport(
        report="",
        root=path,
        scanned=len(specs),
        clean=clean,
        errors=errors,
        findings=findings,
        counts=counts,
        deduped=deduped,
        grade=_grade(len(findings), len(specs)),
    )
    report.report = render_scan(report, mode)
    return report
