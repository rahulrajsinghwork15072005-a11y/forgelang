"""ForgeLang CLI: run programs, REPL, token/AST/bytecode dumps, conformance."""

from __future__ import annotations

import argparse
import sys

from forgelang.driver import (
    assert_conformance,
    dump_bytecode,
    dump_tokens,
    format_error,
    run_source,
)
from forgelang.lexer import tokenize
from forgelang.parser import parse


def read_source(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def cmd_run(args) -> int:
    source = read_source(args.file)
    result = run_source(source, engine=args.engine, budget=args.budget)
    for line in result.output:
        print(line)
    if result.error is not None:
        print(format_error(result.error, source), file=sys.stderr)
        return 70
    if args.dump_tokens:
        print(dump_tokens(source))
    if args.dump_bytecode:
        print(dump_bytecode(source))
    if args.gc_stats:
        s = result.stats
        print(
            f"[gc] allocations={s.gc_allocations} collections={s.gc_collections} "
            f"live={s.gc_live_after}"
        )
        print(f"[steps] {s.steps}")
    return 0


def cmd_conform(args) -> int:
    import glob as _glob

    paths = []
    for pattern in args.files:
        matched = _glob.glob(pattern)
        paths.extend(matched if matched else [pattern])
    failures = 0
    checked = 0
    for path in paths:
        source = read_source(path)
        try:
            assert_conformance(source)
            checked += 1
            if args.verbose:
                print(f"OK   {path}")
        except Exception as exc:  # noqa: BLE001 - report every conformance failure
            failures += 1
            print(f"FAIL {path}: {exc}")
    print(f"{checked}/{checked + failures} conform")
    return 1 if failures else 0


def cmd_repl(_args) -> int:

    print("ForgeLang REPL — engine: vm | type :quit to exit")
    buffer = ""
    while True:
        prompt = "... " if buffer else ">>> "
        try:
            line = input(prompt)
        except EOFError:
            break
        if line.strip() in (":quit", ":q", "exit"):
            break
        buffer += line + "\n"
        if line.strip().endswith(";") or line.strip().endswith("}"):
            source = buffer
            buffer = ""
            result = run_source(source, engine="vm")
            for out_line in result.output:
                print(out_line)
            if result.error is not None:
                print(format_error(result.error, source), file=sys.stderr)


def cmd_dump(args) -> int:
    source = read_source(args.file)
    if args.what == "tokens":
        print(dump_tokens(source))
    elif args.what == "bytecode":
        print(dump_bytecode(source))
    else:
        program = parse(source)

        def render(node, depth=0):
            name = type(node).__name__
            extra = ""
            for attr in ("name", "op", "value"):
                v = getattr(node, attr, None)
                if isinstance(v, str):
                    extra = f" {v!r}"
                    break
            lines = ["  " * depth + f"{name}{extra}"]
            for child in getattr(node, "body", []) or []:
                lines.extend(render(child, depth + 1))
            for attr in ("then", "otherwise", "cond", "value", "left", "right"):
                child = getattr(node, attr, None)
                if child is not None and not isinstance(child, str):
                    lines.extend(render(child, depth + 1))
            return [line for line in lines]

        print("\n".join(render(program)))
        _ = tokenize
    return 0


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="forgelang")
    sub = root.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="run a .fg program")
    run_p.add_argument("file")
    run_p.add_argument("--engine", choices=["interp", "vm"], default="vm")
    run_p.add_argument("--budget", type=int, default=20_000_000)
    run_p.add_argument("--dump-tokens", action="store_true")
    run_p.add_argument("--dump-bytecode", action="store_true")
    run_p.add_argument("--gc-stats", action="store_true")
    run_p.set_defaults(fn=cmd_run)

    conf = sub.add_parser("conform", help="verify both engines agree on files")
    conf.add_argument("files", nargs="+")
    conf.add_argument("-v", "--verbose", action="store_true")
    conf.set_defaults(fn=cmd_conform)

    repl = sub.add_parser("repl", help="interactive session")
    repl.set_defaults(fn=cmd_repl)

    dump = sub.add_parser("dump", help="dump tokens / ast / bytecode")
    dump.add_argument("what", choices=["tokens", "ast", "bytecode"])
    dump.add_argument("file")
    dump.set_defaults(fn=cmd_dump)
    return root


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
