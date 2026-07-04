CATEGORY = "recursion"
ORACLE = "crash"
CANONICAL = {"n": -1}
CANONICAL_SIZE = 1


def buggy(n: int) -> int:
    if n == 0:
        return 0
    return 1 + buggy(n - 1)


def fixed(n: int) -> int:
    return abs(n)
