CATEGORY = "off_by_one"
ORACLE = "differential"
CANONICAL = {"n": 1}
CANONICAL_SIZE = 1


def buggy(n: int) -> int:
    return len(range(1, n))


def fixed(n: int) -> int:
    return len(range(1, n + 1))
