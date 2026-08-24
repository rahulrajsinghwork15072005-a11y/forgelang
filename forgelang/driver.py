"""High-level driver: run source on either engine, conformance checking, dumps."""

from __future__ import annotations

import dataclasses

from .compiler import compile_program, disassemble
from .gc import Heap
from .interp import Interpreter
from .lexer import tokenize
from .parser import parse
from .tokens import ExecStats, ForgeError
from .vm import VM

ENGINES = ("interp", "vm")


@dataclasses.dataclass
class RunResult:
    output: list[str]
    stats: ExecStats
    error: ForgeError | None = None

    def ok(self) -> bool:
        return self.error is None


def run_source(
    source: str,
    engine: str = "interp",
    budget: int = 20_000_000,
    gc_threshold: int = 256,
) -> RunResult:
    if engine not in ENGINES:
        raise ValueError(f"unknown engine {engine!r}")
    out_lines: list[str] = []
    heap = Heap(threshold=gc_threshold)
    stats = ExecStats()
    try:
        program = parse(source)
        if engine == "interp":
            interp = Interpreter(out_lines=out_lines, heap=heap, budget=budget)
            interp.run(program)
            stats.steps = interp.steps
        else:
            proto = compile_program(program)
            vm = VM(proto, heap=heap, out_lines=out_lines, budget=budget)
            vm.run()
            stats.steps = vm.steps
        stats.gc_collections = heap.collections
        stats.gc_allocations = heap.allocations
        stats.gc_live_after = len(heap.objects)
        return RunResult(output=out_lines, stats=stats)
    except ForgeError as exc:
        stats.gc_collections = heap.collections
        stats.gc_allocations = heap.allocations
        return RunResult(output=out_lines, stats=stats, error=exc)


def assert_conformance(source: str) -> tuple[RunResult, RunResult]:
    """Run on both engines; outputs must match byte-for-byte."""
    interp_result = run_source(source, engine="interp")
    vm_result = run_source(source, engine="vm")
    if interp_result.output != vm_result.output:
        raise ConformanceError(
            f"engines disagree:\ninterp={interp_result.output}\nvm={vm_result.output}"
        )
    if interp_result.error is not None or vm_result.error is not None:
        i_msg = interp_result.error.message if interp_result.error else "none"
        v_msg = vm_result.error.message if vm_result.error else "none"
        if i_msg != v_msg:
            raise ConformanceError(f"error disagreement:\ninterp={i_msg}\nvm={v_msg}")
    return interp_result, vm_result


class ConformanceError(Exception):
    pass


def dump_tokens(source: str) -> str:
    tokens = tokenize(source)
    lines = ["LINE  COL  TYPE      LEXEME"]
    for tok in tokens:
        name = tok.type.name
        lexeme = repr(tok.lexeme)
        lines.append(f"{tok.line:<5} {tok.col:<4} {name:<9} {lexeme}")
    return "\n".join(lines)


def dump_bytecode(source: str) -> str:
    program = parse(source)
    proto = compile_program(program)
    return disassemble(proto)


def format_error(exc: ForgeError, source: str) -> str:
    return exc.render(source)


_ = dataclasses
