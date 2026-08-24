"""ForgeLang — a small programming language with two interchangeable backends.

Front end: lexer + precedence-climbing parser producing an AST.
Back ends: a tree-walk interpreter (reference semantics) and a bytecode
compiler driving a stack VM with upvalue closures and a mark-sweep GC.
A conformance harness proves both engines produce identical output.
"""

from .driver import (
    ConformanceError,
    RunResult,
    assert_conformance,
    dump_bytecode,
    dump_tokens,
    run_source,
)
from .gc import Heap
from .tokens import ForgeError

__all__ = [
    "run_source",
    "assert_conformance",
    "dump_tokens",
    "dump_bytecode",
    "Heap",
    "ForgeError",
    "RunResult",
    "ConformanceError",
]
__version__ = "0.1.0"
