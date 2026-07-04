from __future__ import annotations

import importlib.util
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nightman.hunt import hunt
from nightman.models import PropertyPlan

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SEEDS = list(range(4))
MAX_EXAMPLES = 300
MEM_MB = 1536
WALL_S = 90.0


def _load_meta(path: str) -> object:
    spec = importlib.util.spec_from_file_location(f"_fix_{os.path.basename(path)}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _plans_for(oracle: str) -> list[PropertyPlan] | None:
    if oracle == "differential":
        return [PropertyPlan(name="differential", partner="fixed")]
    return None


def _detect(path: str, func: str, oracle: str) -> list:
    results = []
    for seed in SEEDS:
        results.append(
            hunt(
                f"{path}:{func}",
                seed=seed,
                max_examples=MAX_EXAMPLES,
                plans=_plans_for(oracle),
                isolate=True,
                mem_mb=MEM_MB,
                wall_s=WALL_S,
            )
        )
    return results


def _canonical_size(meta: object) -> int:
    return int(getattr(meta, "CANONICAL_SIZE", 0))


def main() -> int:
    fixtures = sorted(f for f in os.listdir(FIXTURE_DIR) if f.endswith(".py") and not f.startswith("_"))
    rows = []
    false_positives = []
    for filename in fixtures:
        path = os.path.join(FIXTURE_DIR, filename)
        meta = _load_meta(path)
        oracle = getattr(meta, "ORACLE", "crash")
        category = getattr(meta, "CATEGORY", filename[:-3])

        detect = _detect(path, "buggy", oracle)
        hits = [r for r in detect if r.status == "failing"]
        detected = bool(hits)
        min_size = min((r.failure.input_size for r in hits), default=None)
        min_ttff = min((r.executions_to_first_failure or 0 for r in hits), default=None)

        guard = _detect(path, "fixed", oracle if oracle != "differential" else "crash")
        fp = [r for r in guard if r.status == "failing"]
        if fp:
            false_positives.append((category, fp[0].failure.args_repr if fp[0].failure else "?"))

        rows.append(
            {
                "category": category,
                "oracle": oracle,
                "detected": detected,
                "trials": f"{len(hits)}/{len(SEEDS)}",
                "min_size": min_size,
                "canonical": _canonical_size(meta),
                "ttff": min_ttff,
                "fp": bool(fp),
            }
        )

    detection_rate = sum(1 for r in rows if r["detected"]) / len(rows)
    fp_rate = sum(1 for r in rows if r["fp"]) / len(rows)
    sizes = [r["min_size"] for r in rows if r["min_size"] is not None]
    ttffs = [r["ttff"] for r in rows if r["ttff"] is not None]
    median_size = statistics.median(sizes) if sizes else 0
    median_ttff = statistics.median(ttffs) if ttffs else 0

    print(f"Nightman eval — {len(rows)} planted bugs, {len(SEEDS)} seeds each\n")
    header = f"{'category':<20} {'oracle':<13} {'detect':<7} {'trials':<7} {'min|canon':<10} {'ttff':<6} fp"
    print(header)
    print("-" * len(header))
    for r in rows:
        size_cell = f"{r['min_size']}|{r['canonical']}"
        detect_cell = "yes" if r["detected"] else "NO"
        fp_cell = "FP" if r["fp"] else "-"
        print(
            f"{r['category']:<20} {r['oracle']:<13} {detect_cell:<7} {r['trials']:<7} "
            f"{size_cell:<10} {str(r['ttff']):<6} {fp_cell}"
        )

    print()
    print(f"detection_rate      : {detection_rate:.0%}  ({sum(1 for r in rows if r['detected'])}/{len(rows)})")
    print(f"false_positive_rate : {fp_rate:.0%}  (must be 0%)")
    print(f"median minimal input: {median_size}")
    print(f"median TTFF (execs) : {median_ttff}")
    for category, example in false_positives:
        print(f"  FALSE POSITIVE on fixed {category}: {example}")

    ok = detection_rate >= 0.9 and fp_rate == 0.0
    print(f"\nRESULT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
