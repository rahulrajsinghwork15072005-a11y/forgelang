# Devlog

Notes from bringing Forgeland's engines into conformance.

## Map literals corrupted the stack

Symptom: after ANY map literal, later `print(has(...))` calls reported
receiving the *print function itself* as an argument, and `m["k"] = v`
complained about assigning into a number. Everything pointed at broken
calls; the calls were innocent.

The compiler emitted map literals as: OP_MAP (push empty dict), then
key/value/SET_INDEX per pair. But the VM's SET_INDEX pops container, key,
value and pushes only the assigned VALUE - so after pair one, the dict was
gone from the stack and the value sat in its slot. Every subsequent stack
consumer shifted by one. The interpreter recursed through a dict directly,
which is why it never noticed.

Fix: build maps like arrays - push all keys and values, then one OP_MAP n
that pops 2n entries and pushes the assembled dict. Changed both the emitter
and the VM handler so the contract is symmetric and documented by the array
path above it.

## Assignment order

`a[i] = v` compiled as value-then-container-then-key while GET_INDEX and the
VM's SET_INDEX expected container, key, value (top-down). Reads worked;
writes assigned into whatever value happened to sit underneath. The
conformance test that caught it printed different results for identical
programs on the two engines - which is exactly what the dual-engine design
is for.

## Property writes crashed the parser

`obj.prop = x` died with NameError inside assignment parsing: GetProp was
referenced but never imported at module level (only lazily inside the dot-
parsing loop). Moved to the normal import block.

## Reconstructed tests

An early version of this repo's test file was accidentally overwritten during
packaging. The class-based suite (TestGC, TestRuntimeErrors,
TestConformance*, TestDiagnostics) was rebuilt from scratch to cover the same
names and behaviors recovered from pytest's cache metadata. Two failures in
the first rebuilt run turned out to be downstream effects of the map-literal
stack bug rather than independent defects - fixed above, tests unchanged.

## GC note

gc_live_after can legitimately differ run-to-run at boundaries (an object is
counted live if reachable OR still pinned since allocation). Tests assert on
survivor minimums, not exact counts.
