CATEGORY = "integer_truncation"
ORACLE = "differential"
CANONICAL = {"xs": [1, 2]}
CANONICAL_SIZE = 2


def buggy(xs: list[int]) -> float:
    if not xs:
        return 0.0
    return sum(xs) // len(xs)


def fixed(xs: list[int]) -> float:
    if not xs:
        return 0.0
    return sum(xs) / len(xs)
