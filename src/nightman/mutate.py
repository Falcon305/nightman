from __future__ import annotations

import ast
from dataclasses import dataclass

_ARITH = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.Div,
    ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mult,
    ast.Mod: ast.Mult,
    ast.Pow: ast.Mult,
}
_COMPARE = {
    ast.Lt: ast.GtE,
    ast.Gt: ast.LtE,
    ast.LtE: ast.Gt,
    ast.GtE: ast.Lt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
}
_BOOL = {ast.And: ast.Or, ast.Or: ast.And}


@dataclass
class Mutant:
    description: str
    line: int
    source: str


def _target_function(tree: ast.Module, name: str) -> ast.AST | None:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


class _Apply(ast.NodeTransformer):
    def __init__(self, target: int) -> None:
        self.target = target
        self.count = 0
        self.description: str | None = None
        self.line = 0

    def _hit(self, line: int) -> bool:
        index = self.count
        self.count += 1
        if index == self.target:
            self.line = line
            return True
        return False

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        op = type(node.op)
        if op in _ARITH and self._hit(node.lineno):
            node.op = _ARITH[op]()
            self.description = f"{op.__name__} to {_ARITH[op].__name__}"
        return node

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        if len(node.ops) == 1 and type(node.ops[0]) in _COMPARE and self._hit(node.lineno):
            op = type(node.ops[0])
            node.ops = [_COMPARE[op]()]
            self.description = f"{op.__name__} to {_COMPARE[op].__name__}"
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        op = type(node.op)
        if op in _BOOL and self._hit(node.lineno):
            node.op = _BOOL[op]()
            self.description = f"{op.__name__} to {_BOOL[op].__name__}"
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, bool):
            if self._hit(node.lineno):
                node.value = not node.value
                self.description = f"{not node.value} to {node.value}"
        elif isinstance(node.value, int) and self._hit(node.lineno):
            node.value = node.value + 1
            self.description = f"integer {node.value - 1} to {node.value}"
        elif isinstance(node.value, float) and self._hit(node.lineno):
            node.value = node.value + 1.0
            self.description = f"float {node.value - 1.0} to {node.value}"
        return node


def _count(source: str, func_name: str) -> int:
    tree = ast.parse(source)
    func = _target_function(tree, func_name)
    if func is None:
        return 0
    counter = _Apply(-1)
    counter.visit(func)
    return counter.count


def mutants(source: str, func_name: str) -> list[Mutant]:
    total = _count(source, func_name)
    out: list[Mutant] = []
    for index in range(total):
        tree = ast.parse(source)
        func = _target_function(tree, func_name)
        if func is None:
            break
        mutator = _Apply(index)
        mutator.visit(func)
        if mutator.description is None:
            continue
        ast.fix_missing_locations(tree)
        out.append(Mutant(description=mutator.description, line=mutator.line, source=ast.unparse(tree)))
    return out
