# ForgeLang architecture

```
 source (.fg)
 │
 ▼
 lexer ──► tokens (type, lexeme, value, line, col) tokens.py / lexer.py
 │
 ▼
 parser ──► AST precedence-climbing (Pratt) parser.py / ast_nodes.py
 │
 ├──────────────────────────────┐
 ▼ ▼
 tree-walk interpreter compiler ──► bytecode Proto interp.py compiler.py
 environments chained by slot resolution: locals /
 parent pointers; closures upvalues / globals at compile
 capture defining env time; jump patching for ifs/loops
 │
 ▼
 stack VM: frames, cells, vm.py
 open/closed upvalues,
 budget counter, GC hooks
 │
 ▼
 Heap: mark-sweep, adaptive threshold, pinning gc.py

 driver.py runs either engine and asserts byte-identical output.
```

## Front end

**Lexer.** Single pass tracking line/column through every advance. Two-char operators
(`== != <= >=`) matched before singles; `//` comments to EOL; strings support `\n \t
\r \" \\` with unterminated/escape errors carrying positions.

**Parser.** Precedence climbing with binding powers: assignment (right-assoc,
validated targets: identifier, index, property) < `or` < `and` < equality <
comparison < additive < multiplicative < unary < call/index/property (looping
postfix chain). Map literals accept string or identifier keys. Statement-level `{`
is always a block — map literals are expressions.

## Tree-walk interpreter

Environments are dicts chained by parent pointers; closures hold their defining
environment, giving shared mutable capture for free. Control flow uses control-flow
exceptions (`ReturnSignal`, `BreakSignal`, `ContinueSignal`) caught at the matching
construct — simple and correct; the bytecode backend exists to show what removing
that overhead buys (~2.6× on recursion).

## Compiler

Scope resolution happens here, so the VM never touches names:

- **Locals**: every function keeps an ordered locals list (slot 0 reserved for the
 callee). Blocks bump a scope depth; leaving a block emits one `POP` per local plus
 `CLOSE_UPVALS` when any of them was captured.
- **Upvalues**: an identifier that isn't local recurses into the enclosing function
 compiler — if found there it's marked captured and becomes `(local=True, index)`;
 otherwise the enclosing's own upvalue index propagates (`(False, idx)`), building
 the classic capture chain.
- **Globals**: top-of-script declarations compile to `DEF_GLOBAL`; unresolved reads
 fall back to runtime `GET_GLOBAL`.
- **Jumps**: forward jumps reserve their operand byte via `emit_jump`;
 `patch_jump` writes the distance to the current end. Backward `LOOP`
 distances are computed against the loop-head index. `continue` in a `for`
 targets the step clause; in a `while`, the condition.

## Stack VM

Frames are `(closure, ip, base)` over one shared value stack; calls push a frame
with `base = len(stack) - argc - 1` so slot 0 is the callee. Recursion is capped
(300 frames).

**Upvalue cells.** A captured local is boxed in a `Cell`. While the owning frame is
alive the cell is *open* — it records the absolute stack position, and reads/writes
go through the stack (so two closures share state). When the frame returns or the
block exits, affected cells *close*: the value copies into the cell and later access
hits the box. This is what makes `make_counter` counters work, including the
per-iteration capture case where each loop body declares a fresh cell.

**Budget.** Every instruction increments a counter; exceeding it aborts with a
runaway-loop error instead of hanging — same guarantee as the interpreter's tick.

## Mark-sweep heap

Arrays, maps, concatenated strings, closures and cells register on allocation. When
the registry crosses a threshold (adaptive: grows to 2× survivors after each cycle)
the collector runs: a gray-stack mark phase walks roots supplied by the engine (VM:
stack + frames + globals + open cells; interpreter: live environments + globals),
then sweeps unregistered entries.

Two soundness details worth naming:

1. **Mid-statement temporaries** would be unreachable to the marker while still in
 use by Python evaluation frames, so freshly allocated objects are *pinned* until
 the next statement boundary (`POP` in the VM, tick in the interpreter).
2. Sweeping only removes objects from ForgeLang's registry — CPython reclaims the
 memory underneath once the last reference drops, which the sweep guarantees.

The interpreter registers environments in a `WeakSet`: live environments mark
themselves; dead ones vanish from the root set automatically.

## Conformance contract

`driver.assert_conformance(src)` requires:

1. identical output lines from both engines, and
2. identical error messages when errors occur.

This turned out to be the project's best testing device: nearly every real bug found
during development (jump-distance off-by-ones, map-literal stack shape, upvalue pair
encoding, script-frame slot alignment) surfaced as an engines-disagree failure rather
than a silent wrong answer.
