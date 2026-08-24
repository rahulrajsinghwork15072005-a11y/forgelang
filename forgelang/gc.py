"""Mark-sweep garbage collector with an adaptive threshold.

Objects (arrays, maps, dynamic strings, closures, upvalue cells) register with
the Heap on allocation. When live-object count crosses the threshold the VM or
interpreter supplies roots and unreachable objects are swept from the registry
(underneath them, Python's own refcounting reclaims memory once we drop refs).
"""

from __future__ import annotations


class Heap:
    def __init__(self, threshold: int = 256) -> None:
        self.objects: list = []
        self.threshold = threshold
        self.allocations = 0
        self.collections = 0
        self.last_live = 0
        self.enabled = True
        self.root_provider = None
        self.pinned: list = []

    def alloc(self, obj) -> object:
        if not self.enabled:
            return obj
        self.objects.append(obj)
        self.pinned.append(obj)
        self.allocations += 1
        if len(self.objects) >= self.threshold:
            self.collect()
        return obj

    def release_pins(self) -> None:
        """Call at statement boundaries: everything live is rooted by then."""
        self.pinned.clear()

    def collect(self, root_iterables=()) -> int:
        marked_ids = set()
        gray = []
        if not root_iterables and self.root_provider is not None:
            root_iterables = self.root_provider()
        pinned_roots = list(self.pinned)

        def mark(value):
            if value is None or isinstance(value, (bool, int, float, str)):
                return
            obj_id = id(value)
            if obj_id in marked_ids:
                return
            marked_ids.add(obj_id)
            gray.append(value)

        for roots in root_iterables:
            for root in roots:
                mark(root)
        for pinned_obj in pinned_roots:
            mark(pinned_obj)

        while gray:
            current = gray.pop()
            if isinstance(current, list):
                for item in current:
                    mark(item)
            elif isinstance(current, dict):
                for key, value in current.items():
                    mark(key)
                    mark(value)
            else:
                for referred in getattr(current, "gc_refs", ()):
                    mark(referred)

        survivors = [obj for obj in self.objects if id(obj) in marked_ids]
        freed = len(self.objects) - len(survivors)
        self.objects = survivors
        self.collections += 1
        self.last_live = len(survivors)
        if len(survivors) > 0:
            self.threshold = max(256, len(survivors) * 2)
        return freed

    def stats(self) -> dict:
        return {
            "allocations": self.allocations,
            "collections": self.collections,
            "live": len(self.objects),
            "threshold": self.threshold,
        }
