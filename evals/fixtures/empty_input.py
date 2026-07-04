CATEGORY = "empty_input"
ORACLE = "crash"
CANONICAL = {"xs": []}
CANONICAL_SIZE = 0


def buggy(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def fixed(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0
