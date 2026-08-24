"""Compound assignment operators: += -= *= /= across both engines."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forgelang.driver import run_source


def assert_agree(src, expected):
    a = run_source(src, "interp")
    b = run_source(src, "vm")
    assert a.error is None, f"interp: {a.error} for {src!r}"
    assert b.error is None, f"vm: {b.error} for {src!r}"
    assert a.output == expected, f"interp: {a.output} != {expected} for {src!r}"
    assert b.output == expected, f"vm: {b.output} != {expected} for {src!r}"


@pytest.mark.parametrize("op,val,expected", [
    ("+=", 5, 15), ("-=", 3, 7), ("*=", 3, 30), ("/=", 5, 2),
])
def test_compound_ident(op, val, expected):
    src = f"let x = 10; x {op} {val}; print(x);"
    assert_agree(src, [str(expected)])


def test_compound_string_concat():
    assert_agree('let s = "ab"; s += "cd"; print(s);', ["abcd"])


def test_compound_in_loop():
    src = """
    let sum = 0;
    for (let i = 1; i <= 4; i += 1) { sum += i; }
    print(sum);
    """
    assert_agree(src, ["10"])


def test_compound_index_target():
    src = """
    let a = [1, 2, 3];
    a[0] += 100; a[2] *= 10;
    print(a[0] + a[1] + a[2]);
    """
    assert_agree(src, ["133"])


def test_compound_with_function_result():
    src = """
    fn five() { return 5; }
    let x = 0;
    x += five();
    print(x);
    """
    assert_agree(src, ["5"])
