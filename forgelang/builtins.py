"""Standard library builtins (pure functions over ForgeLang values)."""

from __future__ import annotations

import math
import time

from .tokens import ForgeError
from .values import BuiltinFn, format_value, type_name


def _num(x, name, line=0, col=0):
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ForgeError(f"{name} expects a number, got {type_name(x)}")
    return x


def make_globals(heap=None, out=None):
    """Returns {name: BuiltinFn}. `out` collects printed lines; default print()."""
    emit = (lambda line: out.append(line)) if out is not None else (lambda line: None)

    def forge_print(*args):
        from .values import format_value

        emit(" ".join(format_value(a) for a in args))

    def fn_len(x):
        if isinstance(x, (list, dict, str)):
            return len(x)
        raise ForgeError(f"len expects array/map/string, got {type_name(x)}")

    def fn_push(arr, value):
        if not isinstance(arr, list):
            raise ForgeError(f"push expects array, got {type_name(arr)}")
        arr.append(value)
        return arr

    def fn_pop(arr):
        if not isinstance(arr, list):
            raise ForgeError(f"pop expects array, got {type_name(arr)}")
        if not arr:
            raise ForgeError("pop from empty array")
        return arr.pop()

    def fn_keys(m):
        if not isinstance(m, dict):
            raise ForgeError(f"keys expects map, got {type_name(m)}")
        return list(m.keys())

    def fn_has(m, key):
        if not isinstance(m, dict):
            raise ForgeError(f"has expects map, got {type_name(m)}")
        return key in m

    def fn_del(m, key):
        if not isinstance(m, dict):
            raise ForgeError(f"del expects map, got {type_name(m)}")
        return m.pop(key, None)

    def fn_abs(x):
        return abs(_num(x, "abs"))

    def fn_floor(x):
        return float(math.floor(_num(x, "floor")))

    def fn_sqrt(x):
        v = _num(x, "sqrt")
        if v < 0:
            raise ForgeError("sqrt of negative number")
        return float(math.sqrt(v))

    def fn_min(a, b):
        a, b = _num(a, "min"), _num(b, "min")
        return min(a, b)

    def fn_max(a, b):
        a, b = _num(a, "max"), _num(b, "max")
        return max(a, b)

    def fn_str(x):
        from .values import format_value

        return format_value(x)

    def fn_num(x):
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            return x
        if isinstance(x, str):
            try:
                return int(x)
            except ValueError:
                try:
                    return float(x)
                except ValueError:
                    raise ForgeError(f"cannot convert '{x}' to number") from None
        raise ForgeError(f"num expects string or number, got {type_name(x)}")

    def fn_type(x):
        return type_name(x)

    def fn_range(a, b=None):
        a_v = int(_num(a, "range"))
        b_v = b if b is None else int(_num(b, "range"))
        start, stop = (0, a_v) if b is None else (a_v, b_v)
        count = max(0, stop - start)
        if count > 1_000_000:
            raise ForgeError("range result too large")
        return [float(i) for i in range(start, stop)]

    def fn_join(arr, sep=","):
        if not isinstance(arr, list):
            raise ForgeError(f"join expects array, got {type_name(arr)}")
        if not isinstance(sep, str):
            raise ForgeError("join separator must be a string")
        parts = [v if isinstance(v, str) else format_value(v) for v in arr]
        return sep.join(parts)

    def fn_split(text, sep=" "):
        if not isinstance(text, str) or not isinstance(sep, str):
            raise ForgeError("split expects strings")
        if sep == "":
            raise ForgeError("split separator cannot be empty")
        return text.split(sep)

    def fn_upper(x):
        if not isinstance(x, str):
            raise ForgeError("upper expects string")
        return x.upper()

    def fn_lower(x):
        if not isinstance(x, str):
            raise ForgeError("lower expects string")
        return x.lower()

    def fn_clock():
        return time.monotonic() * 1000.0

    registry = {
        "print": BuiltinFn("print", forge_print, -1),
        "len": BuiltinFn("len", fn_len, 1),
        "push": BuiltinFn("push", fn_push, 2),
        "pop": BuiltinFn("pop", fn_pop, 1),
        "keys": BuiltinFn("keys", fn_keys, 1),
        "has": BuiltinFn("has", fn_has, 2),
        "del": BuiltinFn("del", fn_del, 2),
        "abs": BuiltinFn("abs", fn_abs, 1),
        "floor": BuiltinFn("floor", fn_floor, 1),
        "sqrt": BuiltinFn("sqrt", fn_sqrt, 1),
        "min": BuiltinFn("min", fn_min, 2),
        "max": BuiltinFn("max", fn_max, 2),
        "str": BuiltinFn("str", fn_str, 1),
        "num": BuiltinFn("num", fn_num, 1),
        "type": BuiltinFn("type", fn_type, 1),
        "range": BuiltinFn("range", fn_range, -1),
        "join": BuiltinFn("join", fn_join, -1),
        "split": BuiltinFn("split", fn_split, -1),
        "upper": BuiltinFn("upper", fn_upper, 1),
        "lower": BuiltinFn("lower", fn_lower, 1),
        "clock": BuiltinFn("clock", fn_clock, 0),
    }
    return registry
