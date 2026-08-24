import pytest

from forgelang.compiler import compile_program, disassemble
from forgelang.gc import Heap
from forgelang.parser import parse
from forgelang.vm import VM


def test_disassemble_lists_opcodes():
    proto = compile_program(parse("print(1 + 2);"))
    text = disassemble(proto)
    assert "GET_GLOBAL" in text
    assert "ADD" in text
    assert "CALL" in text


def test_constant_pool_deduplication():
    proto = compile_program(parse('let a = "same"; let b = "same"; print(a);'))
    script_consts = [c for c in proto.consts if isinstance(c, str)]
    assert script_consts.count("same") == 1


def test_vm_budget_stops_infinite_loop():
    src = "while (true) { }"
    heap = Heap(threshold=64)
    proto = compile_program(parse(src))
    vm = VM(proto, heap=heap, budget=100000)
    from forgelang.tokens import ForgeError

    with pytest.raises(ForgeError) as exc:
        vm.run()
    assert "budget" in str(exc.value)


def test_gc_adaptive_threshold_grows():
    heap = Heap(threshold=8)
    keep = []
    for i in range(50):
        keep.append(heap.alloc([i]))
        heap.root_provider = lambda: [keep]
    assert heap.threshold > 8
    assert heap.collections >= 1
