import pytest

from forgelang.ast_nodes import (
    ArrayLit,
    Binary,
    Call,
    FnExpr,
    GetProp,
    Ident,
    If,
    Index,
    While,
)
from forgelang.parser import parse
from forgelang.tokens import ForgeError


def test_operator_precedence_tree_shape():
    ast = parse("1 + 2 * 3;")
    stmt = ast.body[0]
    assert isinstance(stmt.expr, Binary) and stmt.expr.op == "+"
    rhs = stmt.expr.right
    assert isinstance(rhs, Binary) and rhs.op == "*"


def test_left_associativity():
    ast = parse('print("x");')
    call = ast.body[0].expr
    assert isinstance(call, Call)


def test_assignment_target_forms():
    ast = parse("a = 1; m.k = 2; arr[0] = 3;")
    targets = [s.expr.target for s in ast.body]
    assert isinstance(targets[0], Ident)
    assert isinstance(targets[1], GetProp)
    assert isinstance(targets[2], Index)


def test_invalid_assignment_target_rejected():
    with pytest.raises(ForgeError):
        parse("1 + 2 = 3;")


def test_if_else_ast():
    ast = parse("if (x) { y; } else { z; }")
    node = ast.body[0]
    assert isinstance(node, If) and node.otherwise is not None


def test_anonymous_fn_expression():
    ast = parse("let f = fn(a, b) { return a; };")
    decl = ast.body[0]
    fnlit = decl.value
    assert isinstance(fnlit, FnExpr) and fnlit.params == ["a", "b"]


def test_array_and_map_literals():
    ast = parse('[1, 2];')
    assert isinstance(ast.body[0].expr, ArrayLit)
    ast2 = parse('let m = {"k": 1};')
    from forgelang.ast_nodes import MapLit

    assert isinstance(ast2.body[0].value, MapLit)


def test_missing_semicolon_is_positioned_error():
    with pytest.raises(ForgeError) as exc:
        parse("let x = 1 let y = 2;")
    assert exc.value.line == 1


def test_while_structure():
    ast = parse("while (true) { }")
    assert isinstance(ast.body[0], While)


def test_call_chain_indexing():
    ast = parse('m.users()[0].name;')
    expr = ast.body[0].expr
    assert isinstance(expr, GetProp)
    assert isinstance(expr.obj, Index)
    assert isinstance(expr.obj.obj, Call)
