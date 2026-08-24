"""Tree-walk interpreter: executes the AST directly (reference semantics)."""

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
from .values import (
    BreakSignal,
    Closure,
    ContinueSignal,
    ReturnSignal,
    add_values,
    arith,
    compare,
    deep_eq,
    index_get,
    index_set,
    truthy,
)


class Environment:
    __slots__ = ("values", "parent", "__weakref__")

    def __init__(self, parent=None) -> None:
        self.values: dict[str, object] = {}
        self.parent = parent

    def define(self, name: str, value) -> None:
        self.values[name] = value

    def get(self, name: str, line: int, col: int):
        env = self
        while env is not None:
            if name in env.values:
                return env.values[name]
            env = env.parent
        raise ForgeError(f"undefined variable '{name}'", line, col)

    def assign(self, name: str, value, line: int, col: int) -> None:
        env = self
        while env is not None:
            if name in env.values:
                env.values[name] = value
                return
            env = env.parent
        raise ForgeError(f"undefined variable '{name}'", line, col)


class Interpreter:
    def __init__(self, out_lines: list | None = None, heap=None, budget: int = 50_000_000) -> None:
        import weakref

        self.out = out_lines if out_lines is not None else []
        self.globals = Environment()
        self._envs: weakref.WeakSet = weakref.WeakSet()
        self._envs.add(self.globals)
        from .builtins import make_globals

        for name, fn in make_globals(heap=heap, out=self.out).items():
            self.globals.define(name, fn)
        self.heap = heap
        self.budget = budget
        self.steps = 0
        if heap is not None:
            heap.root_provider = self.get_roots

    def _new_env(self, parent) -> Environment:
        env = Environment(parent)
        self._envs.add(env)
        return env

    def get_roots(self):
        yield [env.values for env in list(self._envs)]
        yield [self.globals.values]

    # ------------------------------------------------------------- execution

    def run(self, program: Program):
        try:
            self.exec_block_stmts(program.body, self.globals)
        except ReturnSignal:
            pass

    def exec_block_stmts(self, stmts, env) -> None:
        for stmt in stmts:
            self.tick()
            self.execute(stmt, env)

    def tick(self) -> None:
        self.steps += 1
        if self.steps > self.budget:
            raise ForgeError("execution budget exceeded (runaway loop?)")
        if self.heap is not None:
            self.heap.release_pins()

    def execute(self, node, env) -> None:
        method = getattr(self, "exec_" + type(node).__name__, None)
        if method is None:
            raise ForgeError(f"cannot execute {type(node).__name__}", node.line, node.col)
        method(node, env)

    # ------------------------------------------------------------ statements

    def exec_VarDecl(self, node: VarDecl, env) -> None:
        value = self.evaluate(node.value, env) if node.value is not None else None
        if self.heap is not None and isinstance(value, (list, dict)):
            self.heap.alloc(value)
        env.define(node.name, value)

    def exec_FnDecl(self, node: FnDecl, env) -> None:
        closure = Closure(node.name, node.params, node.body, env)
        if self.heap is not None:
            self.heap.alloc(closure)
        env.define(node.name, closure)

    def exec_If(self, node: If, env) -> None:
        self.tick()
        if truthy(self.evaluate(node.cond, env)):
            self.execute(node.then, env)
        elif node.otherwise is not None:
            self.execute(node.otherwise, env)

    def exec_While(self, node: While, env) -> None:
        while truthy(self.evaluate(node.cond, env)):
            self.tick()
            try:
                self.execute(node.body, env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def exec_For(self, node: For, env) -> None:
        loop_env = self._new_env(env)
        if node.init is not None:
            self.execute(node.init, loop_env)
        while node.cond is None or truthy(self.evaluate(node.cond, loop_env)):
            self.tick()
            try:
                body_env = self._new_env(loop_env)
                self.exec_block_stmts(_as_body_list(node.body), body_env)
            except BreakSignal:
                break
            except ContinueSignal:
                pass
            if node.step is not None:
                if isinstance(node.step, ExprStmt):
                    self.evaluate(node.step.expr, loop_env)
                else:
                    self.evaluate(node.step, loop_env)

    def exec_Block(self, node: Block, env) -> None:
        block_env = self._new_env(env)
        self.exec_block_stmts(node.body, block_env)

    def exec_Return(self, node: Return, env) -> None:
        value = self.evaluate(node.value, env) if node.value is not None else None
        raise ReturnSignal(value)

    def exec_Break(self, node: Break, env) -> None:
        raise BreakSignal()

    def exec_Continue(self, node: Continue, env) -> None:
        raise ContinueSignal()

    def exec_ExprStmt(self, node: ExprStmt, env) -> None:
        self.evaluate(node.expr, env)

    # ----------------------------------------------------------- expressions

    def evaluate(self, node, env):
        method = getattr(self, "eval_" + type(node).__name__, None)
        if method is None:
            raise ForgeError(f"cannot evaluate {type(node).__name__}", node.line, node.col)
        return method(node, env)

    def eval_Literal(self, node: Literal, env):
        return node.value

    def eval_Ident(self, node: Ident, env):
        return env.get(node.name, node.line, node.col)

    def eval_Assign(self, node: Assign, env):
        target = node.target
        if isinstance(target, Ident):
            value = self.evaluate(node.value, env)
            if self.heap is not None and isinstance(value, (list, dict)):
                self.heap.alloc(value)
            env.assign(target.name, value, target.line, target.col)
            return value
        if isinstance(target, Index):
            obj = self.evaluate(target.obj, env)
            key = self.evaluate(target.index, env)
            value = self.evaluate(node.value, env)
            if self.heap is not None and isinstance(value, (list, dict)):
                self.heap.alloc(value)
            index_set(obj, key, value, target.line, target.col)
            return value
        if type(target).__name__ == "GetProp":
            obj = self.evaluate(target.obj, env)
            value = self.evaluate(node.value, env)
            if not isinstance(obj, dict):
                raise ForgeError(
                    f"cannot set property on {type(obj).__name__}", target.line, target.col
                )
            obj[target.name] = value
            return value
        raise ForgeError("invalid assignment target", node.line, node.col)

    def eval_Unary(self, node: Unary, env):
        value = self.evaluate(node.operand, env)
        if node.op == "-":
            is_num = isinstance(value, (int, float)) and not isinstance(value, bool)
            if not is_num:
                raise ForgeError(
                    f"unary '-' expects number, got {type(value).__name__}",
                    node.line,
                    node.col,
                )
            return -value
        return not truthy(value)

    def eval_Binary(self, node: Binary, env):
        left = self.evaluate(node.left, env)
        right = self.evaluate(node.right, env)
        op = node.op
        if op == "+":
            return add_values(left, right, node.line, node.col)
        return arith(op, left, right, node.line, node.col)

    def eval_Logical(self, node: Logical, env):
        left = self.evaluate(node.left, env)
        if node.op == "and":
            if not truthy(left):
                return left
            return self.evaluate(node.right, env)
        if truthy(left):
            return left
        return self.evaluate(node.right, env)

    def eval_Call(self, node: Call, env):
        callee = self.evaluate(node.callee, env)
        args = [self.evaluate(a, env) for a in node.args]
        return self.call_value(callee, args, node.line, node.col)

    def call_value(self, callee, args, line: int, col: int):
        if isinstance(callee, Closure):
            if len(args) != len(callee.params):
                raise ForgeError(
                    f"{callee.name} expects {len(callee.params)} argument(s), got {len(args)}",
                    line,
                    col,
                )
            frame_env = self._new_env(callee.env)
            for name, arg in zip(callee.params, args):
                frame_env.define(name, arg)
            try:
                self.exec_block_stmts(callee.body.body, frame_env)
            except ReturnSignal as ret:
                return ret.value
            return None
        if hasattr(callee, "fn"):
            arity = callee.arity
            if arity >= 0 and len(args) != arity:
                raise ForgeError(
                    f"{callee.name} expects {arity} argument(s), got {len(args)}", line, col
                )
            return callee.fn(*args)
        raise ForgeError("cannot call a non-function value", line, col)

    def eval_ArrayLit(self, node: ArrayLit, env):
        arr = [self.evaluate(item, env) for item in node.items]
        if self.heap is not None:
            self.heap.alloc(arr)
        return arr

    def eval_MapLit(self, node: MapLit, env):
        m = {}
        for key, value_node in node.pairs:
            m[key] = self.evaluate(value_node, env)
        if self.heap is not None:
            self.heap.alloc(m)
        return m

    def eval_Index(self, node: Index, env):
        obj = self.evaluate(node.obj, env)
        key = self.evaluate(node.index, env)
        return index_get(obj, key, node.line, node.col)

    def eval_GetProp(self, node, env):
        obj = self.evaluate(node.obj, env)
        from .values import get_property

        return get_property(obj, node.name, node.line, node.col)

    eval_FnExpr = None


def _as_body_list(body):
    if isinstance(body, Block):
        return body.body
    return [body]


def _install_comparison():
    original = Interpreter.eval_Binary

    def eval_binary(self, node: Binary, env):
        if node.op in ("==", "!=", "<", ">", "<=", ">="):
            left = self.evaluate(node.left, env)
            right = self.evaluate(node.right, env)
            if node.op == "==":
                return deep_eq(left, right)
            if node.op == "!=":
                return not deep_eq(left, right)
            return compare(node.op, left, right, node.line, node.col)
        return original(self, node, env)

    Interpreter.eval_Binary = eval_binary


_install_comparison()


def _install_fnexpr():
    def eval_FnExpr(self, node: FnExpr, env):
        closure = Closure(node.name, node.params, node.body, env)
        if self.heap is not None:
            self.heap.alloc(closure)
        return closure

    Interpreter.eval_FnExpr = eval_FnExpr


_install_fnexpr()
