# ForgeLang

A complete programming language built from scratch — **lexer → Pratt parser → AST →
two interchangeable backends**: a tree-walk interpreter *and* a bytecode compiler
driving a stack VM with upvalue closures and a mark-sweep garbage collector.

> Pure Python stdlib. Zero dependencies.
> A conformance harness runs every program through **both** engines and requires
> byte-for-byte identical output.

```
workload             engine       time
fib recursion        interp       27.5 ms
fib recursion        vm           11.9 ms      speedup: 2.63x
arithmetic loop      interp      295 ms / vm ≈ parity (globals-traffic bound)
```

## The language

```
fn fib(n) {
  if (n < 2) { return n; }
  return fib(n - 1) + fib(n - 2);
}
print(fib(10));            // 55

fn make_counter(start) {
  let count = start;
  return fn() { count = count + 1; return count; };
}
let next = make_counter(0);
next(); next();            // closures capture mutable state

let m = {name: "forge"};
m.version = 2;             // dot access on maps
[1, 2, 3].push(4);         // bound array methods
```

Features: `let` / `fn` declarations · anonymous functions · first-class functions &
closures (shared mutable capture) · `if/else`, `while`, C-style `for`,
`break`/`continue` · arrays & hash maps with indexing, dot-access, `push/pop/keys`
· strings with escapes and methods · logical short-circuiting (`and`/`or`) · deep
equality · nil · a stdlib (`len push pop keys has del abs floor sqrt min max str num
type range join split upper lower clock print`) · instruction-budget runaway-loop
protection · compiler-style caret diagnostics with line/column on every error.

## Two backends, one semantics

| | tree-walk interpreter | bytecode VM |
|---|---|---|
| dispatch | recursive `evaluate()` over AST | flat opcode loop over `(code, consts)` |
| variables | chained environments | compile-time slot resolution: locals, upvalues, globals |
| closures | captured environment reference | open/closed upvalue cells over frame slots |
| speed (this repo) | baseline | ~2.6× on recursion, parity on globals-heavy loops |

`bench.py --quick` reproduces the table above.

## Conformance testing

```python
from forgelang.driver import assert_conformance
assert_conformance(src)   # raises unless both engines agree exactly
```

Every semantic test in this repo runs each program through both engines and asserts
identical stdout — including identical error messages for runtime failures. The CLI
does it for whole files:

```bash
python cli.py conform examples/*.fg -v
```

## CLI

```bash
python cli.py run examples/fib.fg                 # VM by default
python cli.py run examples/fib.fg --engine interp # tree-walk backend
python cli.py dump tokens examples/fib.fg         # token stream w/ line:col
python cli.py dump bytecode examples/fib.fg       # disassembly
python cli.py run bench-src.fg --gc-stats         # GC collections/live objects
python cli.py repl                                # interactive session
```

Example diagnostics:

```
line 3: division by zero
    print(1/0);
          ^
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) — includes the upvalue cell design
(open → closed transitions), why map literals assemble after their pairs, how the
mark-sweep heap pins mid-statement temporaries to stay sound, and the exact
conformance contract between engines.
