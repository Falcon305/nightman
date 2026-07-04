CATEGORY = "boundary_index"
ORACLE = "crash"
CANONICAL = {"xs": []}
CANONICAL_SIZE = 0


def buggy(xs: list[int]) -> int:
    return xs[1]


def fixed(xs: list[int]) -> int:
    return xs[1] if len(xs) > 1 else -1
