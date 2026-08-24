"""Bytecode: instruction set, chunk model, and the AST -> bytecode compiler.

Scope resolution happens here: identifiers compile to local slots, captured
upvalues (with the recursive capture chain), or globals â€” so the VM never
touches names at runtime.
"""

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
from .tokens import ForgeError

OP_CONST = 0
OP_NIL = 1
OP_TRUE = 2
OP_FALSE = 3
OP_POP = 4
OP_GET_LOCAL = 5
OP_SET_LOCAL = 6
OP_GET_GLOBAL = 7
OP_DEF_GLOBAL = 8
OP_SET_GLOBAL = 9
OP_GET_UPVAL = 10
OP_SET_UPVAL = 11
OP_ADD = 12
OP_SUB = 13
OP_MUL = 14
OP_DIV = 15
OP_MOD = 16
OP_NEG = 17
OP_NOT = 18
OP_EQ = 19
OP_NEQ = 20
OP_LT = 21
OP_LTE = 22
OP_GT = 23
OP_GTE = 24
OP_JMP = 25
OP_JMP_IF_FALSE = 26
OP_JMP_IF_TRUE = 27
OP_LOOP = 28
OP_CALL = 29
OP_RETURN = 30
OP_CLOSURE = 31
OP_CLOSE_UPVALS = 32
OP_LIST = 33
OP_MAP = 34
OP_MAP_KEY = 35
OP_GET_INDEX = 36
OP_SET_INDEX = 37
OP_GET_PROP = 38
OP_COPY = 39

OP_NAMES = {
    OP_CONST: "CONST",
    OP_NIL: "NIL",
    OP_TRUE: "TRUE",
    OP_FALSE: "FALSE",
    OP_POP: "POP",
    OP_GET_LOCAL: "GET_LOCAL",
    OP_SET_LOCAL: "SET_LOCAL",
    OP_GET_GLOBAL: "GET_GLOBAL",
    OP_DEF_GLOBAL: "DEF_GLOBAL",
    OP_SET_GLOBAL: "SET_GLOBAL",
    OP_GET_UPVAL: "GET_UPVAL",
    OP_SET_UPVAL: "SET_UPVAL",
    OP_ADD: "ADD",
    OP_SUB: "SUB",
    OP_MUL: "MUL",
    OP_DIV: "DIV",
    OP_MOD: "MOD",
    OP_NEG: "NEG",
    OP_NOT: "NOT",
    OP_EQ: "EQ",
    OP_NEQ: "NEQ",
    OP_LT: "LT",
    OP_LTE: "LTE",
    OP_GT: "GT",
    OP_GTE: "GTE",
    OP_JMP: "JMP",
    OP_JMP_IF_FALSE: "JMP_IF_FALSE",
    OP_JMP_IF_TRUE: "JMP_IF_TRUE",
    OP_LOOP: "LOOP",
    OP_CALL: "CALL",
    OP_RETURN: "RETURN",
    OP_CLOSURE: "CLOSURE",
    OP_CLOSE_UPVALS: "CLOSE_UPVALS",
    OP_LIST: "LIST",
    OP_MAP: "MAP",
    OP_MAP_KEY: "MAP_KEY",
    OP_GET_INDEX: "GET_INDEX",
    OP_SET_INDEX: "SET_INDEX",
    OP_GET_PROP: "GET_PROP",
    OP_COPY: "COPY",
}

_SIMPLE_OPS = {
    "+": OP_ADD,
    "-": OP_SUB,
    "*": OP_MUL,
    "/": OP_DIV,
    "%": OP_MOD,
    "==": OP_EQ,
    "!=": OP_NEQ,
    "<": OP_LT,
    "<=": OP_LTE,
    ">": OP_GT,
    ">=": OP_GTE,
}


class Proto:
    __slots__ = ("arity", "code", "consts", "lines", "name", "upvals")

    def __init__(self, name: str, arity: int) -> None:
        self.name = name
        self.arity = arity
        self.code: list[int] = []
        self.consts: list = []
        self.lines: list[int] = []
        self.upvals: list[tuple[bool, int]] = []

    def forge_type(self) -> str:
        return f"<proto {self.name}>"

    def gc_refs(self):
        return [c for c in self.consts if isinstance(c, (list, dict, Proto))]


class ClosureObj:
    __slots__ = ("proto", "upvals")

    def __init__(self, proto: Proto, upvals: list) -> None:
        self.proto = proto
        self.upvals = upvals

    def forge_type(self) -> str:
        return f"<fn {self.proto.name}>"

    def forge_repr(self) -> str:
        return f"<fn {self.proto.name}/{self.proto.arity}>"


class Cell:
    """Upvalue box. While open, ``pos`` indexes the owning frame's stack;
    on close the value is copied into ``value`` and ``pos`` becomes None."""

    __slots__ = ("pos", "value")

    def __init__(self, pos=None) -> None:
        self.value = None
        self.pos = pos

    def gc_refs(self):
        return [self.value]


class Local:
    __slots__ = ("depth", "is_captured", "name")

    def __init__(self, name: str, depth: int) -> None:
        self.name = name
        self.depth = depth
        self.is_captured = False


class FnCompiler:
    def __init__(self, name: str, arity: int, enclosing=None, fn_scope_depth: int = 0) -> None:
        self.proto = Proto(name, arity)
        self.enclosing = enclosing
        self.locals: list[Local] = [Local("", 0)]
        self.scope_depth = fn_scope_depth
        self.loop_stack: list[list[int]] = []
        self.continue_targets: list[list[int]] = []

    def emit(self, op: int, line: int = 0, operand: int | None = None) -> int:
        self.proto.code.append(op)
        if operand is not None:
            self.proto.code.append(operand)
        self.proto.lines.append(line)
        return len(self.proto.code) - 1

    def make_const(self, value) -> int:
        for i, existing in enumerate(self.proto.consts):
            if type(existing) is type(value) and existing == value:
                return i
        self.proto.consts.append(value)
        return len(self.proto.consts) - 1

    def patch_jump(self, offset_index: int) -> None:
        jump = offset_index + 1
        distance = len(self.proto.code) - jump - 1
        self.proto.code[jump] = distance

    def emit_loop(self, loop_start: int, line: int) -> None:
        self.emit(OP_LOOP, line)
        distance = len(self.proto.code) + 1 - loop_start
        self.proto.code.append(distance)


class Compiler:
    """Drives FnCompilers for nested function scopes."""

    def __init__(self) -> None:
        self.current = FnCompiler("script", 0)

    # ------------------------------------------------------------- plumbing

    def _begin_fn(self, name: str, params: list[str]) -> None:
        self.current = FnCompiler(name, len(params), enclosing=self.current)

    def _end_fn(self) -> Proto:
        proto = self.current.proto
        self.emit_current(OP_RETURN, 0)
        self.current = self.current.enclosing
        return proto

    def emit_current(self, op: int, line: int, operand: int | None = None) -> int:
        return self.current.emit(op, line, operand)

    def emit_jump(self, op: int, line: int) -> int:
        """Forward jump: reserves the offset operand; returns opcode index."""
        self.emit_current(op, line)
        self.current.proto.code.append(0)
        return len(self.current.proto.code) - 2

    def emit_loop(self, loop_start: int, line: int) -> None:
        self.current.emit_loop(loop_start, line)

    # ------------------------------------------------------------ top level

    def compile_program(self, program: Program) -> Proto:
        for stmt in program.body:
            self.stmt(stmt)
        self.emit_current(OP_RETURN, 0)
        return self.current.proto

    # ----------------------------------------------------------- statements

    def stmt(self, node) -> None:
        method = getattr(self, "s_" + type(node).__name__)
        method(node)

    def s_VarDecl(self, node: VarDecl) -> None:
        current = self.current
        name = node.name
        is_script_global = current.enclosing is None and current.scope_depth == 0
        if not is_script_global:
            for local in reversed(current.locals[1:]):
                if local.depth < current.scope_depth:
                    break
                if local.name == name and local.depth == current.scope_depth:
                    raise ForgeError(
                        f"variable '{name}' already declared in this scope", node.line, node.col
                    )
        if is_script_global:
            if node.value is not None:
                self.expr(node.value)
            else:
                self.emit_current(OP_NIL, node.line)
            self.emit_current(OP_DEF_GLOBAL, node.line, current.make_const(name))
            return
        current.locals.append(Local(name, current.scope_depth))
        if node.value is not None:
            self.expr(node.value)
        else:
            self.emit_current(OP_NIL, node.line)

    def s_FnDecl(self, node: FnDecl) -> None:
        current = self.current
        is_script_global = current.enclosing is None and current.scope_depth == 0
        if is_script_global:
            self._function(node.name, node.params, node.body, node.line)
            self.emit_current(OP_DEF_GLOBAL, node.line, current.make_const(node.name))
            return
        current.locals.append(Local(node.name, current.scope_depth))
        self._function(node.name, node.params, node.body, node.line)

    def _function(self, name: str, params: list[str], body: Block, line: int) -> None:
        self._begin_fn(name, params)
        fn = self.current
        for param in params:
            fn.locals.append(Local(param, fn.scope_depth + 1))
        fn.scope_depth += 1
        for stmt in body.body:
            self.stmt(stmt)
        proto = self._end_fn()
        const_idx = self.current.make_const(proto)
        self.emit_current(OP_CLOSURE, line, const_idx)
        for is_local, index in proto.upvals:
            self.current.proto.code.append(1 if is_local else 0)
            self.current.proto.code.append(index)
            self.current.proto.lines.append(line)
            self.current.proto.lines.append(line)

    def s_If(self, node: If) -> None:
        self.expr(node.cond)
        then_jump = self.emit_jump(OP_JMP_IF_FALSE, node.line)
        self.stmt(node.then)
        else_jump = self.emit_jump(OP_JMP, node.line)
        self.current.patch_jump(then_jump)
        if node.otherwise is not None:
            self.stmt(node.otherwise)
        self.current.patch_jump(else_jump)

    def s_While(self, node: While) -> None:
        loop_start = len(self.current.proto.code)
        self.current.loop_stack.append([])
        self.current.continue_targets.append([])
        self.expr(node.cond)
        exit_jump = self.emit_jump(OP_JMP_IF_FALSE, node.line)
        self.stmt(node.body)
        self._patch_continues(loop_start)
        self.emit_loop(loop_start, node.line)
        self.current.patch_jump(exit_jump)
        self._patch_breaks()

    def s_For(self, node: For) -> None:
        if node.init is not None:
            self.stmt(node.init)
        loop_start = len(self.current.proto.code)
        self.current.loop_stack.append([])
        self.current.continue_targets.append([])
        if node.cond is not None:
            self.expr(node.cond)
            exit_jump = self.emit_jump(OP_JMP_IF_FALSE, node.line)
        else:
            exit_jump = -1
        self.stmt(node.body)
        continue_target = len(self.current.proto.code)
        self._patch_continues(continue_target)
        if node.step is not None:
            step = node.step
            if isinstance(step, ExprStmt):
                self.expr(step.expr)
            else:
                self.expr(step)
            self.emit_current(OP_POP, node.line)
        self.emit_loop(loop_start, node.line)
        if exit_jump != -1:
            self.current.patch_jump(exit_jump)
        self._patch_breaks()

    def _patch_continues(self, target: int) -> None:
        targets = self.current.continue_targets[-1]
        for j_op in targets:
            j = j_op + 1
            distance = (j + 1) - target
            code = self.current.proto.code
            code[j_op] = OP_LOOP
            code[j] = distance
        self.current.continue_targets[-1] = []

    def _patch_breaks(self) -> None:
        jumps = self.current.loop_stack.pop()
        for j in jumps:
            self.current.patch_jump(j)
        self.current.continue_targets.pop()

    def s_Return(self, node: Return) -> None:
        if node.value is not None:
            self.expr(node.value)
        else:
            self.emit_current(OP_NIL, node.line)
        self.emit_current(OP_RETURN, node.line)

    def s_Break(self, node: Break) -> None:
        if not self.current.loop_stack:
            raise ForgeError("'break' outside of a loop", node.line, node.col)
        jump = self.emit_jump(OP_JMP, node.line)
        self.current.loop_stack[-1].append(jump)

    def s_Continue(self, node: Continue) -> None:
        if not self.current.continue_targets:
            raise ForgeError("'continue' outside of a loop", node.line, node.col)
        jump = self.emit_jump(OP_JMP, node.line)
        self.current.continue_targets[-1].append(jump)

    def s_Block(self, node: Block) -> None:
        current = self.current
        current.scope_depth += 1
        locals_before = len(current.locals)
        for inner in node.body:
            self.stmt(inner)
        captured = any(loc.is_captured for loc in current.locals[locals_before:])
        if captured:
            self.emit_current(OP_CLOSE_UPVALS, node.line, locals_before)
        for _ in range(len(current.locals) - locals_before):
            self.emit_current(OP_POP, node.line)
        del current.locals[locals_before:]
        current.scope_depth -= 1

    def s_ExprStmt(self, node: ExprStmt) -> None:
        self.expr(node.expr)
        self.emit_current(OP_POP, node.line)

    # ----------------------------------------------------------- expressions

    def expr(self, node) -> None:
        method = getattr(self, "e_" + type(node).__name__)
        method(node)

    def e_Literal(self, node: Literal) -> None:
        if node.value is None:
            self.emit_current(OP_NIL, node.line)
        elif node.value is True:
            self.emit_current(OP_TRUE, node.line)
        elif node.value is False:
            self.emit_current(OP_FALSE, node.line)
        else:
            self.emit_current(OP_CONST, node.line, self.current.make_const(node.value))

    def e_Ident(self, node: Ident) -> None:
        self._load_named(node.name, node.line)

    def _load_named(self, name: str, line: int) -> None:
        slot = self._resolve_local(self.current, name)
        if slot != -1:
            self.emit_current(OP_GET_LOCAL, line, slot)
            return
        upval = self._resolve_upvalue(self.current, name)
        if upval != -1:
            self.emit_current(OP_GET_UPVAL, line, upval)
            return
        self.emit_current(OP_GET_GLOBAL, line, self.current.make_const(name))

    def _store_named(self, name: str, line: int) -> bool:
        slot = self._resolve_local(self.current, name)
        if slot != -1:
            self.emit_current(OP_SET_LOCAL, line, slot)
            return False
        upval = self._resolve_upvalue(self.current, name)
        if upval != -1:
            self.emit_current(OP_SET_UPVAL, line, upval)
            return False
        self.emit_current(OP_SET_GLOBAL, line, self.current.make_const(name))
        return True

    def _resolve_local(self, compiler: FnCompiler, name: str) -> int:
        for i in range(len(compiler.locals) - 1, 0, -1):
            if compiler.locals[i].name == name:
                return i
        return -1

    def _resolve_upvalue(self, compiler: FnCompiler, name: str) -> int:
        if compiler.enclosing is None:
            return -1
        slot = self._resolve_local_strict(compiler.enclosing, name)
        if slot != -1:
            compiler.enclosing.locals[slot].is_captured = True
            return self._add_upvalue(compiler, True, slot)
        parent_upval = self._resolve_upvalue(compiler.enclosing, name)
        if parent_upval != -1:
            return self._add_upvalue(compiler, False, parent_upval)
        return -1

    def _resolve_local_strict(self, compiler: FnCompiler, name: str) -> int:
        for i in range(len(compiler.locals) - 1, 0, -1):
            if compiler.locals[i].name == name:
                return i
        return -1

    def _add_upvalue(self, compiler: FnCompiler, is_local: bool, index: int) -> int:
        proto = compiler.proto
        for i, (existing_local, existing_index) in enumerate(proto.upvals):
            if existing_local == is_local and existing_index == index:
                return i
        proto.upvals.append((is_local, index))
        return len(proto.upvals) - 1

    def e_Assign(self, node: Assign) -> None:
        target = node.target
        if isinstance(target, Ident):
            self.expr(node.value)
            self._store_named(target.name, target.line)
            return
        if isinstance(target, Index):
            self.expr(target.obj)
            self.expr(target.index)
            self.expr(node.value)
            self.emit_current(OP_SET_INDEX, target.line)
            return
        if isinstance(target, GetProp):
            self.expr(target.obj)
            key_idx = self.current.make_const(target.name)
            self.emit_current(OP_CONST, target.line, key_idx)
            self.expr(node.value)
            self.emit_current(OP_SET_INDEX, target.line)
            return
        raise ForgeError("invalid assignment target", node.line, node.col)

    def e_Unary(self, node: Unary) -> None:
        self.expr(node.operand)
        self.emit_current(OP_NEG if node.op == "-" else OP_NOT, node.line)

    def e_Binary(self, node: Binary) -> None:
        self.expr(node.left)
        self.expr(node.right)
        op = _SIMPLE_OPS.get(node.op)
        if op is None:
            raise ForgeError(f"unsupported operator {node.op}", node.line, node.col)
        self.emit_current(op, node.line)

    def e_Logical(self, node: Logical) -> None:
        self.expr(node.left)
        self.emit_current(OP_COPY, node.line)
        if node.op == "and":
            jump = self.emit_jump(OP_JMP_IF_FALSE, node.line)
        else:
            jump = self.emit_jump(OP_JMP_IF_TRUE, node.line)
        self.emit_current(OP_POP, node.line)
        self.expr(node.right)
        self.current.patch_jump(jump)

    def e_Call(self, node: Call) -> None:
        self.expr(node.callee)
        for arg in node.args:
            self.expr(arg)
        self.emit_current(OP_CALL, node.line, len(node.args))

    def e_Index(self, node: Index) -> None:
        self.expr(node.obj)
        self.expr(node.index)
        self.emit_current(OP_GET_INDEX, node.line)

    def e_GetProp(self, node) -> None:
        self.expr(node.obj)
        key_idx = self.current.make_const(node.name)
        self.emit_current(OP_GET_PROP, node.line, key_idx)

    def e_ArrayLit(self, node: ArrayLit) -> None:
        for item in node.items:
            self.expr(item)
        self.emit_current(OP_LIST, node.line, len(node.items))

    def e_MapLit(self, node: MapLit) -> None:
        # emit every key/value pair first, then assemble: OP_MAP pops
        # 2*n entries and pushes one map (same shape as ArrayLit/OP_LIST)
        for key, value_node in node.pairs:
            key_idx = self.current.make_const(key)
            self.emit_current(OP_CONST, node.line, key_idx)
            self.expr(value_node)
        self.emit_current(OP_MAP, node.line, len(node.pairs))

    def e_FnExpr(self, node: FnExpr) -> None:
        self._function(node.name or "anon", node.params, node.body, node.line)


def compile_program(program: Program) -> Proto:
    compiler = Compiler()
    return compiler.compile_program(program)


def disassemble(proto: Proto, name: str = "script") -> str:
    lines = [f"== {name} =="]
    code = proto.code
    i = 0
    while i < len(code):
        op = code[i]
        op_name = OP_NAMES.get(op, f"?{op}")
        line_no = proto.lines[i] if i < len(proto.lines) else 0
        if op in (
            OP_CONST,
            OP_GET_GLOBAL,
            OP_DEF_GLOBAL,
            OP_SET_GLOBAL,
            OP_CLOSURE,
        ):
            const = proto.consts[code[i + 1]]
            shown = const.name if hasattr(const, "name") else repr(const)
            lines.append(f"{i:04d} {line_no:>4} {op_name:<12} {shown}")
            step = 2
        elif op in (
            OP_GET_LOCAL,
            OP_SET_LOCAL,
            OP_GET_UPVAL,
            OP_SET_UPVAL,
            OP_CALL,
            OP_LIST,
            OP_MAP,
            OP_CLOSE_UPVALS,
            OP_GET_PROP,
        ):
            lines.append(f"{i:04d} {line_no:>4} {op_name:<12} {code[i + 1]}")
            step = 2
        elif op in (OP_JMP, OP_JMP_IF_FALSE, OP_JMP_IF_TRUE, OP_LOOP):
            lines.append(f"{i:04d} {line_no:>4} {op_name:<12} -> {i + 1 + code[i + 1]}")
            step = 2
        else:
            lines.append(f"{i:04d} {line_no:>4} {op_name}")
            step = 1
        i += step
    return "\n".join(lines)
