import pytest

from forgelang.lexer import tokenize
from forgelang.tokens import ForgeError, T


def types(src):
    return [t.type for t in tokenize(src)]


def test_keywords_and_identifiers():
    toks = tokenize("let fn if else while for return break continue true false nil and or")
    assert all(t.type in {T.LET, T.FN, T.IF, T.ELSE, T.WHILE, T.FOR, T.RETURN,
                          T.BREAK, T.CONTINUE, T.TRUE, T.FALSE, T.NIL, T.AND, T.OR}
               for t in toks[:-1])


def test_int_vs_float():
    toks = tokenize("42 3.14 7")
    assert [t.value for t in toks[:-1]] == [42, 3.14, 7]
    assert toks[0].type == T.INT and toks[1].type == T.FLOAT


def test_string_escapes():
    toks = tokenize('"a\\n\\t\\"q\\\\"')
    assert toks[0].value == 'a\n\t"q\\'


def test_line_col_tracking():
    src = "let a = 1;\nlet b = 2;"
    toks = tokenize(src)
    b_tok = next(t for t in toks if t.lexeme == "b")
    assert b_tok.line == 2
    semi = [t for t in toks if t.type == T.SEMICOLON]
    assert semi[0].line == 1 and semi[1].line == 2


def test_comments_ignored():
    toks = tokenize("1 // trailing comment\n2 // eof comment")
    nums = [t for t in toks if t.type == T.INT]
    assert len(nums) == 2


def test_unterminated_string_raises_position():
    with pytest.raises(ForgeError) as exc:
        tokenize('"never closed')
    assert exc.value.line == 1


def test_unexpected_char():
    with pytest.raises(ForgeError) as exc:
        tokenize("let @ = 1;")
    assert "@" in str(exc.value)


def test_two_char_ops():
    toks = tokenize("== != <= >=")
    assert [t.type for t in toks[:-1]] == [T.EQ, T.NEQ, T.LTE, T.GTE]


def test_eof_token_present():
    toks = tokenize("")
    assert toks[-1].type == T.EOF
