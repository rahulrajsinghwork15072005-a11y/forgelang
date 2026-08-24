"""Runtime value semantics: truthiness, equality, formatting, containers."""

from __future__ import annotations

from .tokens import ForgeError


def truthy(value) -> bool:
    return not (value is False or value is None)


def deep_eq(a, b, depth: int = 0) -> bool:
    if depth > 64:
        raise ForgeError("equality nesting too deep")
    if type(a) is not type(b):
        return a is b or (a is None and b is None)
    if isinstance(a, list):
        if len(a) != len(b):
            return False
        return all(deep_eq(x, y, depth + 1) for x, y in zip(a, b))
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return False
        return all(deep_eq(v, b[k], depth + 1) for k, v in a.items())
    return a == b


def compare(op: str, a, b, line: int, col: int) -> bool:
    ok_numbers = isinstance(a, (int, float)) and isinstance(b, (int, float))
    ok_strings = isinstance(a, str) and isinstance(b, str)
    if not (ok_numbers or ok_strings):
        raise ForgeError(
            f"cannot compare {type_name(a)} and {type_name(b)} with '{op}'", line, col
        )
    if op == "<":
        return a < b
    if op == ">":
        return a > b
    if op == "<=":
        return a <= b
    return a >= b



def set_property(obj, name: str, value, line: int, col: int) -> None:
    if isinstance(obj, dict):
        obj[name] = value
        return
    raise ForgeError(f"cannot set property '{name}' on {type_name(obj)}", line, col)

def add_values(a, b, line: int, col: int):
    both_numbers = isinstance(a, (int, float)) and isinstance(b, (int, float))
    both_strings = isinstance(a, str) and isinstance(b, str)
    if both_numbers:
        return a + b
    if both_strings:
        return a + b
    raise ForgeError(f"cannot add {type_name(a)} and {type_name(b)}", line, col)


def arith(op: str, a, b, line: int, col: int):
    if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        raise ForgeError(
            f"{op} expects numbers, got {type_name(a)} and {type_name(b)}", line, col
        )
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0:
            raise ForgeError("division by zero", line, col)
        result = a / b
        return result
    if op == "%":
        if b == 0:
            raise ForgeError("modulo by zero", line, col)
        return a % b
    raise ForgeError(f"unknown operator {op}", line, col)


def index_get(obj, key, line: int, col: int):
    if isinstance(obj, list):
        idx = _as_index(key, line, col, len(obj))
        return obj[idx]
    if isinstance(obj, dict):
        return obj.get(key)
    raise ForgeError(f"cannot index {type_name(obj)}", line, col)


def index_set(obj, key, value, line: int, col: int) -> None:
    if isinstance(obj, list):
        idx = _as_index(key, line, col, len(obj))
        obj[idx] = value
        return
    if isinstance(obj, dict):
        if not isinstance(key, str):
            raise ForgeError("map keys must be strings", line, col)
        obj[key] = value
        return
    raise ForgeError(f"cannot assign into {type_name(obj)}", line, col)


def get_property(obj, name: str, line: int, col: int):
    from .builtins import BuiltinFn

    if isinstance(obj, dict):
        if name in obj:
            return obj[name]
        raise ForgeError(f"map has no key '{name}'", line, col)
    if isinstance(obj, list):
        if name == "push":
            def push(value):
                obj.append(value)
                return None

            return BuiltinFn("push", push, 1)
        if name == "pop":
            def pop():
                if not obj:
                    raise ForgeError("pop from empty array", line, col)
                return obj.pop()

            return BuiltinFn("pop", pop, 0)
        raise ForgeError(f"arrays have no method '{name}'", line, col)
    if isinstance(obj, str):
        if name == "upper":
            return BuiltinFn("upper", lambda: obj.upper(), 0)
        if name == "lower":
            return BuiltinFn("lower", lambda: obj.lower(), 0)
        if name == "len":
            return len(obj)
    raise ForgeError(f"cannot access property '{name}' on {type_name(obj)}", line, col)


def _as_index(key, line: int, col: int, length: int) -> int:
    if not isinstance(key, (int, float)) or (isinstance(key, float) and not key.is_integer()):
        raise ForgeError("array index must be an integer", line, col)
    idx = int(key)
    if idx < 0 or idx >= length:
        raise ForgeError(f"index {idx} out of bounds (length {length})", line, col)
    return idx


def format_value(value) -> str:
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e16:
        return str(int(value))
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "[" + ", ".join(format_element(v) for v in value) + "]"
    if isinstance(value, dict):
        inner = ", ".join(
            f"{k}: {format_element(v)}" for k, v in value.items()
        )
        return "{" + inner + "}"
    if hasattr(value, "forge_repr"):
        return value.forge_repr()
    return str(value)


def format_element(value) -> str:
    if isinstance(value, str):
        return '"' + value + '"'
    return format_value(value)


def type_name(value) -> str:
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "map"
    if hasattr(value, "forge_type"):
        return value.forge_type()
    return "value"


class BuiltinFn:
    __slots__ = ("name", "fn", "arity")

    def __init__(self, name: str, fn, arity) -> None:
        self.name = name
        self.fn = fn
        self.arity = arity

    def forge_type(self) -> str:
        return f"<native fn {self.name}>"


class Closure:
    """Tree-walk closure: params/body AST plus captured environment."""

    __slots__ = ("name", "params", "body", "env")

    def __init__(self, name, params, body, env) -> None:
        self.name = name or "<anon>"
        self.params = params
        self.body = body
        self.env = env

    def forge_type(self) -> str:
        return f"<fn {self.name}>"

    def forge_repr(self) -> str:
        return f"<fn {self.name}/{len(self.params)}>"


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


class ReturnSignal(Exception):
    def __init__(self, value) -> None:
        super().__init__()
        self.value = value
