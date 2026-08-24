"""Precedence-climbing (Pratt-style) parser: tokens -> AST."""

from __future__ import annotations

from .ast_nodes import (
    ArrayLit,
    Assign,
    Binary,
    Block,
    Break,
    Call,
    Continue,
    ExprStmt,
    FnDecl,
    FnExpr,
    For,
    GetProp,
    Ident,
    If,
    Index,
    Literal,
    Logical,
    MapLit,
    Program,
    Return,
    Unary,
    VarDecl,
    While,
)
from .tokens import T, Token

_ASSIGN_RIGHT = 2
_LOGICAL_OR = 4
_LOGICAL_AND = 5
_EQUALITY = 7
_COMPARISON = 8
_TERM = 10
_FACTOR = 12
_UNARY = 14
_CALL = 16

_BINOPS = {
    T.PLUS: ("+", _TERM),
    T.MINUS: ("-", _TERM),
    T.STAR: ("*", _FACTOR),
    T.SLASH: ("/", _FACTOR),
    T.PERCENT: ("%", _FACTOR),
    T.EQ: ("==", _EQUALITY),
    T.NEQ: ("!=", _EQUALITY),
    T.LT: ("<", _COMPARISON),
    T.LTE: ("<=", _COMPARISON),
    T.GT: (">", _COMPARISON),
    T.GTE: (">=", _COMPARISON),
}


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # ------------------------------------------------------------- plumbing

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.type != T.EOF:
            self.pos += 1
        return tok

    def check(self, ttype: T) -> bool:
        return self.peek().type == ttype

    def match(self, *types: T) -> Token | None:
        if self.peek().type in types:
            return self.advance()
        return None

    def expect(self, ttype: T, message: str) -> Token:
        if self.check(ttype):
            return self.advance()
        tok = self.peek()
        got = tok.lexeme if tok.type != T.EOF else "end of input"
        raise SyntaxErr(f"{message} (got '{got}')", tok.line, tok.col)

    # ------------------------------------------------------------ entrypoint

    def parse_program(self) -> Program:
        body = []
        while not self.check(T.EOF):
            body.append(self.declaration())
        return Program(body=body)

    # ----------------------------------------------------------- statements

    def declaration(self):
        if self.match(T.LET):
            return self.var_decl()
        if self.check(T.FN) and self.tokens[self.pos + 1].type == T.IDENT:
            return self.fn_decl()
        return self.statement()

    def var_decl(self) -> VarDecl:
        name_tok = self.expect(T.IDENT, "expected variable name after 'let'")
        value = None
        if self.match(T.ASSIGN):
            value = self.expression()
        self.expect(T.SEMICOLON, "expected ';' after variable declaration")
        node = VarDecl(name=name_tok.value, value=value)
        node.line, node.col = name_tok.line, name_tok.col
        return node

    def fn_decl(self) -> FnDecl:
        fn_tok = self.advance()
        name_tok = self.expect(T.IDENT, "expected function name")
        params = self.param_list()
        body = self.block()
        node = FnDecl(name=name_tok.value, params=params, body=body)
        node.line, node.col = fn_tok.line, fn_tok.col
        return node

    def param_list(self) -> list[str]:
        self.expect(T.LPAREN, "expected '(' after function name")
        names = []
        if not self.check(T.RPAREN):
            while True:
                names.append(self.expect(T.IDENT, "expected parameter name").value)
                if not self.match(T.COMMA):
                    break
        self.expect(T.RPAREN, "expected ')' after parameters")
        return names

    def statement(self):
        tok = self.peek()
        if self.match(T.IF):
            return self.if_statement(tok)
        if self.match(T.WHILE):
            return self.while_statement(tok)
        if self.match(T.FOR):
            return self.for_statement(tok)
        if self.match(T.RETURN):
            node = Return(value=None if self.check(T.SEMICOLON) else self.expression())
            self.expect(T.SEMICOLON, "expected ';' after return value")
            node.line, node.col = tok.line, tok.col
            return node
        if self.match(T.BREAK):
            self.expect(T.SEMICOLON, "expected ';' after 'break'")
            node = Break()
            node.line, node.col = tok.line, tok.col
            return node
        if self.match(T.CONTINUE):
            self.expect(T.SEMICOLON, "expected ';' after 'continue'")
            node = Continue()
            node.line, node.col = tok.line, tok.col
            return node
        if self.check(T.LBRACE):
            return self.block()
        expr = self.expression()
        self.expect(T.SEMICOLON, "expected ';' after expression")
        node = ExprStmt(expr=expr)
        node.line, node.col = tok.line, tok.col
        return node

    def if_statement(self, tok):
        self.expect(T.LPAREN, "expected '(' after 'if'")
        cond = self.expression()
        self.expect(T.RPAREN, "expected ')' after condition")
        then = self.statement()
        otherwise = self.statement() if self.match(T.ELSE) else None
        node = If(cond=cond, then=then, otherwise=otherwise)
        node.line, node.col = tok.line, tok.col
        return node

    def while_statement(self, tok):
        self.expect(T.LPAREN, "expected '(' after 'while'")
        cond = self.expression()
        self.expect(T.RPAREN, "expected ')' after condition")
        body = self.statement()
        node = While(cond=cond, body=body)
        node.line, node.col = tok.line, tok.col
        return node

    def for_statement(self, tok):
        self.expect(T.LPAREN, "expected '(' after 'for'")
        init = None
        if self.match(T.SEMICOLON):
            pass
        elif self.match(T.LET):
            init = self.var_decl()
        else:
            expr = self.expression()
            self.expect(T.SEMICOLON, "expected ';' after for-clause")
            init = ExprStmt(expr=expr)

        cond = None if self.check(T.SEMICOLON) else self.expression()
        self.expect(T.SEMICOLON, "expected ';' after loop condition")

        step = None
        if not self.check(T.RPAREN):
            target = self.expression()
            if self.match(T.ASSIGN):
                step = Assign(target=target, value=self.assignment())
            else:
                step = ExprStmt(expr=target)

        self.expect(T.RPAREN, "expected ')' after for clauses")
        body = self.statement()
        node = For(init=init, cond=cond, step=step, body=body)
        node.line, node.col = tok.line, tok.col
        return node

    def block(self) -> Block:
        open_tok = self.expect(T.LBRACE, "expected '{'")
        body = []
        while not self.check(T.RBRACE) and not self.check(T.EOF):
            body.append(self.declaration())
        self.expect(T.RBRACE, "expected '}' to close block")
        node = Block(body=body)
        node.line, node.col = open_tok.line, open_tok.col
        return node

    # ----------------------------------------------------------- expressions

    def expression(self):
        return self.assignment()

    def assignment(self):
        left = self.binary(_ASSIGN_RIGHT + 1)
        if self.check(T.ASSIGN):
            eq_tok = self.advance()
            if not isinstance(left, (Ident, Index, GetProp)):
                raise SyntaxErr(
                    "invalid assignment target", eq_tok.line, eq_tok.col
                )
            value = self.assignment()
            node = Assign(target=left, value=value)
            node.line, node.col = eq_tok.line, eq_tok.col
            return node
        return left

    def binary(self, min_bp: int):
        left = self.unary()
        while True:
            tok = self.peek()
            if tok.type == T.AND or tok.type == T.OR:
                op = "and" if tok.type == T.AND else "or"
                bp = _LOGICAL_AND if op == "and" else _LOGICAL_OR
                if bp < min_bp:
                    return left
                self.advance()
                right = self.binary(bp + 1)
                node = Logical(op=op, left=left, right=right)
                node.line, node.col = tok.line, tok.col
                left = node
                continue
            info = _BINOPS.get(tok.type)
            if info is None:
                return left
            op, bp = info
            if bp < min_bp:
                return left
            self.advance()
            right = self.binary(bp + 1)
            node = Binary(op=op, left=left, right=right)
            node.line, node.col = tok.line, tok.col
            left = node

    def unary(self):
        tok = self.peek()
        if tok.type in (T.MINUS, T.BANG):
            self.advance()
            operand = self.unary()
            node = Unary(op="-" if tok.type == T.MINUS else "!", operand=operand)
            node.line, node.col = tok.line, tok.col
            return node
        return self.call_chain()

    def call_chain(self):
        expr = self.primary()
        while True:
            tok = self.peek()
            if tok.type == T.LPAREN:
                self.advance()
                args = []
                if not self.check(T.RPAREN):
                    args.append(self.expression())
                    while self.match(T.COMMA):
                        args.append(self.expression())
                self.expect(T.RPAREN, "expected ')' after arguments")
                node = Call(callee=expr, args=args)
                node.line, node.col = tok.line, tok.col
                expr = node
            elif tok.type == T.LBRACKET:
                self.advance()
                index = self.expression()
                close = self.expect(T.RBRACKET, "expected ']' after index")
                node = Index(obj=expr, index=index)
                node.line, node.col = close.line, close.col
                expr = node
            elif tok.type == T.DOT:
                self.advance()
                name = self.expect(T.IDENT, "expected property name after '.'")
                from .ast_nodes import GetProp

                node = GetProp(obj=expr, name=name.value)
                node.line, node.col = name.line, name.col
                expr = node
            else:
                return expr

    def primary(self) -> object:
        tok = self.peek()
        if tok.type in (T.INT, T.FLOAT, T.STRING):
            self.advance()
            node = Literal(value=tok.value)
            node.line, node.col = tok.line, tok.col
            return node
        if self.match(T.TRUE):
            node = Literal(value=True)
            node.line, node.col = tok.line, tok.col
            return node
        if self.match(T.FALSE):
            node = Literal(value=False)
            node.line, node.col = tok.line, tok.col
            return node
        if self.match(T.NIL):
            node = Literal(value=None)
            node.line, node.col = tok.line, tok.col
            return node
        if self.match(T.IDENT):
            node = Ident(name=tok.value)
            node.line, node.col = tok.line, tok.col
            return node
        if self.match(T.LPAREN):
            inner = self.expression()
            self.expect(T.RPAREN, "expected ')' after expression")
            return inner
        if self.match(T.LBRACKET):
            items = []
            if not self.check(T.RBRACKET):
                items.append(self.expression())
                while self.match(T.COMMA):
                    items.append(self.expression())
            self.expect(T.RBRACKET, "expected ']' after array literal")
            node = ArrayLit(items=items)
            node.line, node.col = tok.line, tok.col
            return node
        if self.match(T.LBRACE):
            pairs = []
            while not self.check(T.RBRACE):
                key_tok = self.peek()
                valid_key = key_tok.type in (T.STRING, T.IDENT) or key_tok.type in KEYWORD_KEYS
                if valid_key:
                    self.advance()
                    key = str(key_tok.value)
                else:
                    raise SyntaxErr("expected map key", key_tok.line, key_tok.col)
                self.expect(T.COLON, "expected ':' after map key")
                pairs.append((key, self.expression()))
                if not self.match(T.COMMA):
                    break
            self.expect(T.RBRACE, "expected '}' after map literal")
            node = MapLit(pairs=pairs)
            node.line, node.col = tok.line, tok.col
            return node
        if self.match(T.FN):
            params = self.param_list()
            body = self.block()
            node = FnExpr(name=None, params=params, body=body)
            node.line, node.col = tok.line, tok.col
            return node
        raise SyntaxErr(f"unexpected token '{tok.lexeme or 'end of input'}'", tok.line, tok.col)


KEYWORD_KEYS = {T.LET, T.FN, T.IF, T.RETURN, T.TRUE, T.FALSE, T.NIL}


def SyntaxErr(message: str, line: int, col: int):
    from .tokens import ForgeError

    return ForgeError(message, line, col)


def parse(source: str) -> Program:
    from .lexer import tokenize

    tokens = tokenize(source)
    return Parser(tokens).parse_program()
