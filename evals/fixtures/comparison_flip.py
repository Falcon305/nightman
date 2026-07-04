CATEGORY = "comparison_flip"
ORACLE = "differential"
CANONICAL = {"x": 0, "lo": 0, "hi": -1}
CANONICAL_SIZE = 2


def buggy(x: int, lo: int, hi: int) -> int:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def fixed(x: int, lo: int, hi: int) -> int:
    return max(lo, min(x, hi))
