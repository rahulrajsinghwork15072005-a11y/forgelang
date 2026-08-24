"""Lexer: source text -> tokens with line/column positions."""

from __future__ import annotations

from .tokens import KEYWORDS, T, Token

_SINGLE = {
    "+": T.PLUS,
    "-": T.MINUS,
    "*": T.STAR,
    "/": T.SLASH,
    "%": T.PERCENT,
    "(": T.LPAREN,
    ")": T.RPAREN,
    "{": T.LBRACE,
    "}": T.RBRACE,
    "[": T.LBRACKET,
    "]": T.RBRACKET,
    ",": T.COMMA,
    ";": T.SEMICOLON,
    ":": T.COLON,
    ".": T.DOT,
}

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    line = 1
    col = 1
    n = len(source)

    def advance(k=1):
        nonlocal i, line, col
        for _ in range(k):
            if i < n and source[i] == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1

    while i < n:
        ch = source[i]
        if ch in " \t\r\n":
            advance()
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                advance()
            continue

        start_line, start_col = line, col
        if ch.isdigit():
            j = i
            while j < n and source[j].isdigit():
                j += 1
            is_float = False
            if j < n and source[j] == "." and j + 1 < n and source[j + 1].isdigit():
                is_float = True
                j += 1
                while j < n and source[j].isdigit():
                    j += 1
            text = source[i:j]
            value = float(text) if is_float else int(text)
            tokens.append(Token(T.FLOAT if is_float else T.INT, text, value, start_line, start_col))
            advance(j - i)
            continue

        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            text = source[i:j]
            ktype = KEYWORDS.get(text, T.IDENT)
            tokens.append(Token(ktype, text, text, start_line, start_col))
            advance(j - i)
            continue

        if ch == '"':
            advance()
            out = []
            while True:
                if i >= n:
                    raise SyntaxErr("unterminated string", start_line, start_col)
                c = source[i]
                if c == '"':
                    advance()
                    break
                if c == "\n":
                    raise SyntaxErr("unterminated string", start_line, start_col)
                if c == "\\":
                    advance()
                    esc = source[i] if i < n else ""
                    if esc not in _ESCAPES:
                        raise SyntaxErr(f"bad escape \\{esc}", line, col)
                    out.append(_ESCAPES[esc])
                    advance()
                else:
                    out.append(c)
                    advance()
            tokens.append(
                Token(T.STRING, "".join(out), "".join(out), start_line, start_col)
            )
            continue

        two = source[i : i + 2]
        if two in ("==", "!=", "<=", ">=", "+=", "-=", "*=", "/="):
            ttype = {
                "==": T.EQ,
                "!=": T.NEQ,
                "<=": T.LTE,
                ">=": T.GTE,
                "+=": T.PLUSEQ,
                "-=": T.MINUSEQ,
                "*=": T.STAREQ,
                "/=": T.SLASHEQ,
            }[two]
            tokens.append(Token(ttype, two, two, start_line, start_col))
            advance(2)
            continue

        if ch == "=":
            tokens.append(Token(T.ASSIGN, "=", "=", start_line, start_col))
            advance()
            continue
        if ch == "!":
            tokens.append(Token(T.BANG, "!", "!", start_line, start_col))
            advance()
            continue
        if ch in "<>":
            tokens.append(Token(T.LT if ch == "<" else T.GT, ch, ch, start_line, start_col))
            advance()
            continue

        if ch in _SINGLE:
            tokens.append(Token(_SINGLE[ch], ch, ch, start_line, start_col))
            advance()
            continue

        raise SyntaxErr(f"unexpected character {ch!r}", start_line, start_col)

    tokens.append(Token(T.EOF, "", None, line, col))
    return tokens


def SyntaxErr(message: str, line: int, col: int):
    from .tokens import ForgeError

    return ForgeError(message, line, col)
