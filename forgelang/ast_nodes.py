"""AST node definitions."""

from __future__ import annotations

from dataclasses import dataclass


class Node:
    line: int = 0
    col: int = 0


@dataclass
class Program(Node):
    body: list


@dataclass
class Block(Node):
    body: list


@dataclass
class VarDecl(Node):
    name: str
    value: object


@dataclass
class FnDecl(Node):
    name: str
    params: list
    body: Block


@dataclass
class If(Node):
    cond: object
    then: object
    otherwise: object | None


@dataclass
class While(Node):
    cond: object
    body: object


@dataclass
class For(Node):
    init: object | None
    cond: object | None
    step: object | None
    body: object


@dataclass
class Return(Node):
    value: object | None


@dataclass
class Break(Node):
    pass


@dataclass
class Continue(Node):
    pass


@dataclass
class ExprStmt(Node):
    expr: object


@dataclass
class Assign(Node):
    target: object
    value: object


@dataclass
class Binary(Node):
    op: str
    left: object
    right: object


@dataclass
class Logical(Node):
    op: str
    left: object
    right: object


@dataclass
class Unary(Node):
    op: str
    operand: object


@dataclass
class Call(Node):
    callee: object
    args: list


@dataclass
class Index(Node):
    obj: object
    index: object


@dataclass
class GetProp(Node):
    obj: object
    name: str


@dataclass
class Literal(Node):
    value: object


@dataclass
class Ident(Node):
    name: str


@dataclass
class ArrayLit(Node):
    items: list


@dataclass
class MapLit(Node):
    pairs: list


@dataclass
class FnExpr(Node):
    name: str | None
    params: list
    body: Block
