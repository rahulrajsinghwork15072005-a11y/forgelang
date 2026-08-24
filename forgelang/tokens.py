"""Token model and error/diagnostic types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class T(Enum):
    IDENT = auto()
    INT = auto()
    FLOAT = auto()
    STRING = auto()

    LET = auto()
    FN = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    RETURN = auto()
    BREAK = auto()
    CONTINUE = auto()
    TRUE = auto()
    FALSE = auto()
    NIL = auto()
    AND = auto()
    OR = auto()

    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PLUSEQ = auto()
    MINUSEQ = auto()
    STAREQ = auto()
    SLASHEQ = auto()
    PERCENT = auto()
    ASSIGN = auto()
    EQ = auto()
    NEQ = auto()
    LT = auto()
    LTE = auto()
    GT = auto()
    GTE = auto()
    BANG = auto()

    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    SEMICOLON = auto()
    COLON = auto()
    DOT = auto()

    EOF = auto()


KEYWORDS = {
    "let": T.LET,
    "fn": T.FN,
    "if": T.IF,
    "else": T.ELSE,
    "while": T.WHILE,
    "for": T.FOR,
    "return": T.RETURN,
    "break": T.BREAK,
    "continue": T.CONTINUE,
    "true": T.TRUE,
    "false": T.FALSE,
    "nil": T.NIL,
    "and": T.AND,
    "or": T.OR,
}


@dataclass(frozen=True)
class Token:
    type: T
    lexeme: str
    value: object
    line: int
    col: int


class ForgeError(Exception):
    """Compile-time or runtime error carrying a source position."""

    def __init__(self, message: str, line: int = 0, col: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col

    def render(self, source: str) -> str:
        lines = source.split("\n")
        if not (1 <= self.line <= len(lines)):
            return f"error: {self.message}"
        src_line = lines[self.line - 1]
        caret_pad = " " * max(0, self.col - 1)
        return (
            f"line {self.line}: {self.message}\n"
            f"    {src_line}\n"
            f"    {caret_pad}^"
        )


@dataclass
class ExecStats:
    steps: int = 0
    gc_collections: int = 0
    gc_allocations: int = 0
    gc_live_after: int = 0
    out_lines: list = field(default_factory=list)
