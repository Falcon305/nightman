CATEGORY = "off_by_one"
ORACLE = "differential"
CANONICAL = {"lo": 0, "hi": 0}
CANONICAL_SIZE = 2


def buggy(lo: int, hi: int) -> int:
    return hi - lo


def fixed(lo: int, hi: int) -> int:
    return hi - lo + 1
