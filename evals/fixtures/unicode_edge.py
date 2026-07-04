CATEGORY = "unicode_edge"
ORACLE = "crash"
CANONICAL = {"label": "€"}
CANONICAL_SIZE = 1


def buggy(label: str) -> bytes:
    return label.encode("ascii")


def fixed(label: str) -> bytes:
    return label.encode("utf-8")
