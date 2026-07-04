import ast

CATEGORY = "unsafe_eval"
ORACLE = "crash"
CANONICAL = {"expr": ""}
CANONICAL_SIZE = 0


def buggy(expr: str) -> object:
    return eval(expr)


def fixed(expr: str) -> object:
    try:
        return ast.literal_eval(expr)
    except (ValueError, SyntaxError):
        return None
