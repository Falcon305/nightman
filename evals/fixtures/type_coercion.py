CATEGORY = "type_coercion"
ORACLE = "crash"
CANONICAL = {"n": 0}
CANONICAL_SIZE = 1


def buggy(n: int) -> str:
    return "id_" + n


def fixed(n: int) -> str:
    return "id_" + str(n)
