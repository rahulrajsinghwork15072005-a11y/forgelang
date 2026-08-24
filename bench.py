"""Benchmark: tree-walk interpreter vs bytecode VM."""

from __future__ import annotations

import argparse
import time

from forgelang.driver import run_source

FIB_SRC = """
fn fib(n) {
  if (n < 2) { return n; }
  return fib(n - 1) + fib(n - 2);
}
fib(20);
"""

LOOP_SRC = """
let total = 0;
for (let i = 0; i < 200000; i = i + 1) {
  total = total + i % 7;
}
total;
"""


def bench(name: str, src: str, engine: str) -> float:
    start = time.perf_counter()
    result = run_source(src, engine=engine)
    elapsed = time.perf_counter() - start
    status = "ok" if result.ok() else f"ERR {result.error.message}"
    print(f"{name:<22} {engine:<8} {elapsed*1000:>9.1f} ms   [{status}]")
    return elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description="ForgeLang engine benchmark")
    parser.add_argument("--quick", action="store_true", help="smaller workloads")
    args = parser.parse_args()

    fib_src = FIB_SRC.replace("fib(20)", "fib(16)") if args.quick else FIB_SRC
    loop_src = LOOP_SRC.replace("200000", "50000") if args.quick else LOOP_SRC

    print(f"{'workload':<22} {'engine':<8} {'time':>12}")
    print("-" * 56)
    t_interp_fib = bench("fib recursion", fib_src, "interp")
    t_vm_fib = bench("fib recursion", fib_src, "vm")
    t_interp_loop = bench("arithmetic loop", loop_src, "interp")
    t_vm_loop = bench("arithmetic loop", loop_src, "vm")

    print("-" * 56)
    if t_vm_fib > 0:
        print(f"speedup fib : {t_interp_fib / t_vm_fib:.2f}x")
    if t_vm_loop > 0:
        print(f"speedup loop: {t_interp_loop / t_vm_loop:.2f}x")


if __name__ == "__main__":
    main()
