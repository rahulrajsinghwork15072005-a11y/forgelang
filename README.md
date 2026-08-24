# Forgeland

A small dynamically-typed programming language with **two interchangeable
execution engines**: a tree-walking interpreter and a bytecode compiler with
a register-free stack VM. Every feature is tested for *conformance* - both
engines must produce identical output or the build fails.

Also has a mark-sweep garbage collector with allocation stats, closures with
captured environments, arrays/maps, and a REPL.

## Language tour

```
let fib = fn(n) {
  if (n < 2) { return n; }
  return fib(n-1) + fib(n-2);
};
print(fib(10));                      // 55

let user = {"name": "ada", "tags": ["pioneer"]};
user["year"] = 1815;
print(user.name + " " + str(user.year));

let counter = fn() {
  let n = 0;
  return fn() { n = n + 1; return n; };
};
let next = counter();
print(next()); print(next());        // 1, 2

for (let i = 0; i < 3; i = i + 1) {
  if (i == 1) { continue; }
  print(i);
}
```

Builtins: `print len push pop keys has del abs floor sqrt min max str num
type range join split upper lower`

## Running

```bash
python cli.py script.fl              # bytecode VM (default)
python cli.py --engine interp script.fl
python cli.py                        # REPL
python -m pytest tests -v            # conformance suite
```

## Why two engines?

A tree-walking interpreter is the reference: direct, obvious, hard to get
wrong. A compiler+VM is faster but reorders reality onto a stack, where
bugs hide as phantom values several instructions away. Running every test
on both and diffing outputs turns engine disagreements into instant,
localized failures. This caught three real defects during development:

1. Map literals corrupted the value stack (compiler/VM contract mismatch).
2. Index assignment emitted `value, obj, key` but the VM pops `value, key,
   obj` - so `m["k"] = v` assigned into whatever sat below.
3. Property-write parsing crashed on a missing import.

See DEVLOG.md for how each surfaced.

## GC

Allocations of arrays/maps/closures/cells register with a Heap. Crossing a
threshold triggers mark-sweep from roots (VM stack, frames, globals, open
upvalues / interpreter environment chain). Newly allocated objects are
pinned until the next statement boundary so a collection can never reap the
object currently being constructed.
