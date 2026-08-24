"""Stack VM: executes compiled bytecode with call frames and upvalue cells."""

from __future__ import annotations

from . import compiler as C
from .builtins import make_globals
from .compiler import (
    Cell,
    Proto,
)
from .tokens import ForgeError
from .values import arith, compare, deep_eq, format_value, truthy


class VmClosure:
    __slots__ = ("proto", "upvals")

    def __init__(self, proto: Proto, upvals: list) -> None:
        self.proto = proto
        self.upvals = upvals

    def forge_type(self) -> str:
        return f"<fn {self.proto.name}>"

    def forge_repr(self) -> str:
        return f"<fn {self.proto.name}/{self.proto.arity}>"


class Frame:
    __slots__ = ("closure", "ip", "base")

    def __init__(self, closure: VmClosure, base: int) -> None:
        self.closure = closure
        self.ip = 0
        self.base = base


class VM:
    def __init__(
        self,
        proto: Proto,
        heap=None,
        out_lines: list | None = None,
        budget: int = 50_000_000,
        trace: bool = False,
    ) -> None:
        self.heap = heap
        self.out = out_lines if out_lines is not None else []
        self.budget = budget
        self.trace = trace
        script = VmClosure(proto, [])
        self.stack: list = [None]
        self.frames: list[Frame] = [Frame(script, 0)]
        self.globals: dict[str, object] = {}
        for name, fn in make_globals(heap=heap, out=self.out).items():
            self.globals[name] = fn
        self.open_upvals: list[tuple[int, object]] = []
        self.steps = 0

    # ------------------------------------------------------------------ run

    def run(self):
        frame = self.frames[-1]
        code = frame.closure.proto.code
        while True:
            self.steps += 1
            if self.steps > self.budget:
                raise ForgeError("execution budget exceeded (runaway loop?)")
            op = code[frame.ip]
            frame.ip += 1
            if self.trace:
                from .compiler import OP_NAMES

                print(
                    f"[trace] ip={frame.ip - 1:04d} {OP_NAMES.get(op, str(op)):<14} "
                    f"stack={self.stack[-5:]}"
                )

            if op == C.OP_CONST:
                self._push(frame.closure.proto.consts[code[frame.ip]])
                frame.ip += 1
            elif op == C.OP_NIL:
                self._push(None)
            elif op == C.OP_TRUE:
                self._push(True)
            elif op == C.OP_FALSE:
                self._push(False)
            elif op == C.OP_POP:
                self.stack.pop()
                if self.heap is not None:
                    self.heap.release_pins()
            elif op == C.OP_GET_LOCAL:
                slot = code[frame.ip]
                frame.ip += 1
                self._push(self.stack[frame.base + slot])
            elif op == C.OP_SET_LOCAL:
                slot = code[frame.ip]
                frame.ip += 1
                self.stack[frame.base + slot] = self.stack[-1]
            elif op == C.OP_GET_GLOBAL:
                name = frame.closure.proto.consts[code[frame.ip]]
                frame.ip += 1
                if name not in self.globals:
                    raise ForgeError(f"undefined variable '{name}'")
                self._push(self.globals[name])
            elif op == C.OP_DEF_GLOBAL:
                name = frame.closure.proto.consts[code[frame.ip]]
                frame.ip += 1
                self.globals[name] = self.stack.pop()
            elif op == C.OP_SET_GLOBAL:
                name = frame.closure.proto.consts[code[frame.ip]]
                frame.ip += 1
                if name not in self.globals:
                    raise ForgeError(f"undefined variable '{name}'")
                self.globals[name] = self.stack[-1]
            elif op == C.OP_GET_UPVAL:
                idx = code[frame.ip]
                frame.ip += 1
                cell = frame.closure.upvals[idx]
                if cell.pos is not None:
                    self._push(self.stack[cell.pos])
                else:
                    self._push(cell.value)
            elif op == C.OP_SET_UPVAL:
                idx = code[frame.ip]
                frame.ip += 1
                cell = frame.closure.upvals[idx]
                if cell.pos is not None:
                    self.stack[cell.pos] = self.stack[-1]
                else:
                    cell.value = self.stack[-1]
            elif op == C.OP_ADD:
                b = self.stack.pop()
                a = self.stack.pop()
                if isinstance(a, str) and isinstance(b, str):
                    result = a + b
                    if self.heap is not None:
                        self.heap.alloc(result)
                else:
                    from .values import add_values

                    result = add_values(a, b, 0, 0)
                self._push(result)
            elif op in (C.OP_SUB, C.OP_MUL, C.OP_DIV, C.OP_MOD):
                b = self.stack.pop()
                a = self.stack.pop()
                op_str = {C.OP_SUB: "-", C.OP_MUL: "*", C.OP_DIV: "/", C.OP_MOD: "%"}[op]
                self._push(arith(op_str, a, b, 0, 0))
            elif op == C.OP_NEG:
                v = self.stack[-1]
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise ForgeError("unary '-' expects a number")
                self.stack[-1] = -v
            elif op == C.OP_NOT:
                self.stack[-1] = not truthy(self.stack[-1])
            elif op == C.OP_EQ:
                b = self.stack.pop()
                a = self.stack.pop()
                self._push(deep_eq(a, b))
            elif op == C.OP_NEQ:
                b = self.stack.pop()
                a = self.stack.pop()
                self._push(not deep_eq(a, b))
            elif op in (C.OP_LT, C.OP_LTE, C.OP_GT, C.OP_GTE):
                b = self.stack.pop()
                a = self.stack.pop()
                op_str = {C.OP_LT: "<", C.OP_LTE: "<=", C.OP_GT: ">", C.OP_GTE: ">="}[op]
                self._push(compare(op_str, a, b, 0, 0))
            elif op == C.OP_JMP:
                offset = code[frame.ip]
                frame.ip += 1
                frame.ip += offset
            elif op == C.OP_JMP_IF_FALSE:
                offset = code[frame.ip]
                frame.ip += 1
                if not truthy(self.stack.pop()):
                    frame.ip += offset
            elif op == C.OP_JMP_IF_TRUE:
                offset = code[frame.ip]
                frame.ip += 1
                if truthy(self.stack.pop()):
                    frame.ip += offset
            elif op == C.OP_LOOP:
                offset = code[frame.ip]
                frame.ip += 1
                frame.ip -= offset
            elif op == C.OP_CALL:
                argc = code[frame.ip]
                frame.ip += 1
                self.call_value(self.stack[-argc - 1], argc)
                frame = self.frames[-1]
                code = frame.closure.proto.code
            elif op == C.OP_RETURN:
                if len(self.stack) > frame.base:
                    result = self.stack.pop()
                else:
                    result = None
                frame = self.frames.pop()
                self._close_upvalues(frame.base)
                del self.stack[frame.base :]
                if not self.frames:
                    return result
                self._push(result)
                frame = self.frames[-1]
                code = frame.closure.proto.code
            elif op == C.OP_CLOSURE:
                const_idx = code[frame.ip]
                frame.ip += 1
                proto = frame.closure.proto.consts[const_idx]
                upvals = []
                for _ in proto.upvals:
                    is_local = code[frame.ip] == 1
                    index = code[frame.ip + 1]
                    frame.ip += 2
                    if is_local:
                        cell = self._capture_open(frame.base + index)
                    else:
                        cell = frame.closure.upvals[index]
                    upvals.append(cell)
                closure = VmClosure(proto, upvals)
                if self.heap is not None:
                    self.heap.alloc(closure)
                self._push(closure)
            elif op == C.OP_CLOSE_UPVALS:
                slot_from = code[frame.ip]
                frame.ip += 1
                self._close_upvalues(frame.base + slot_from)
            elif op == C.OP_LIST:
                count = code[frame.ip]
                frame.ip += 1
                if count:
                    arr = self.stack[-count:]
                    del self.stack[-count:]
                else:
                    arr = []
                if self.heap is not None:
                    self.heap.alloc(arr)
                self._push(arr)
            elif op == C.OP_MAP:
                count = code[frame.ip]
                frame.ip += 1
                total = count * 2
                entries = self.stack[-total:] if total else []
                if total:
                    del self.stack[-total:]
                m: dict = {}
                for k in range(0, total, 2):
                    key = entries[k]
                    value = entries[k + 1]
                    m[key] = value
                if self.heap is not None:
                    self.heap.alloc(m)
                self._push(m)
            elif op == C.OP_GET_INDEX:
                key = self.stack.pop()
                obj = self.stack.pop()
                self._push(index_get(obj, key))
            elif op == C.OP_SET_INDEX:
                value = self.stack.pop()
                key = self.stack.pop()
                obj = self.stack.pop()
                index_set(obj, key, value)
                self._push(value)
            elif op == C.OP_COPY:
                self._push(self.stack[-1])
            elif op == C.OP_GET_PROP:
                name = frame.closure.proto.consts[code[frame.ip]]
                frame.ip += 1
                obj = self.stack[-1]
                from .values import get_property

                self.stack[-1] = get_property(obj, name, 0, 0)
            else:
                raise ForgeError(f"unknown opcode {op}")

    # ------------------------------------------------------------- helpers

    def _push(self, value) -> None:
        self.stack.append(value)

    def call_value(self, callee, argc: int) -> None:
        args = self.stack[-argc:] if argc else []

        if isinstance(callee, VmClosure):
            if argc != callee.proto.arity:
                raise ForgeError(
                    f"{callee.proto.name} expects {callee.proto.arity} argument(s), got {argc}"
                )
            base = len(self.stack) - argc - 1
            if len(self.frames) >= 300:
                raise ForgeError("stack overflow (recursion too deep)")
            self.frames.append(Frame(callee, base))

        elif hasattr(callee, "fn"):
            arity = callee.arity
            if arity >= 0 and argc != arity:
                raise ForgeError(
                    f"{callee.name} expects {arity} argument(s), got {argc}"
                )
            args = self.stack[-argc:] if argc else []
            del self.stack[-(argc + 1):]
            result = callee.fn(*args)
            self._push(result)
        else:
            raise ForgeError("cannot call a non-function value")

    def _capture_open(self, stack_pos: int):
        for pos, cell in self.open_upvals:
            if pos == stack_pos:
                return cell
        cell = Cell(pos=stack_pos)
        if self.heap is not None:
            self.heap.alloc(cell)
        self.open_upvals.append((stack_pos, cell))
        self.open_upvals.sort(key=lambda pc: pc[0], reverse=True)
        return cell

    def _close_upvalues(self, from_pos: int) -> None:
        remaining = []
        for pos, cell in self.open_upvals:
            if pos >= from_pos:
                cell.value = self.stack[pos] if pos < len(self.stack) else None
                cell.pos = None
            else:
                remaining.append((pos, cell))
        self.open_upvals = remaining

    def get_roots(self):
        yield self.stack
        yield self.frames
        yield self.globals.values()
        yield [cell for _, cell in self.open_upvals]


def index_get(obj, key):
    from .values import index_get as ig

    return ig(obj, key, 0, 0)


def index_set(obj, key, value):
    from .values import index_set as iset

    iset(obj, key, value, 0, 0)


_ = format_value
