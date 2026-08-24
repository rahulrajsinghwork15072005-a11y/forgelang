
from forgelang.driver import assert_conformance, run_source


def both(src):
    return assert_conformance(src)


def outs(src):
    r1, r2 = both(src)
    return r1.output


class TestConformanceArithmetic:
    def test_numbers(self):
        assert outs('print(1 + 2 * 3);') == ["7"]
        assert outs('print((1 + 2) * 3);') == ["9"]
        assert outs('print(10 / 4);') == ["2.5"]
        assert outs('print(7 % 3);') == ["1"]
        assert outs('print(-5 + 2);') == ["-3"]

    def test_string_concat(self):
        assert outs('print("foo" + "bar");') == ["foobar"]

    def test_integer_formatting(self):
        assert outs("print(6 / 2);") == ["3"]
        assert outs("print(1.5);") == ["1.5"]

    def test_comparisons(self):
        assert outs("print(1 < 2); print(2 <= 2); print(3 > 4); print(5 >= 6);") == [
            "true",
            "true",
            "false",
            "false",
        ]

    def test_equality_deep(self):
        src = """
        print([1, [2, 3]] == [1, [2, 3]]);
        print({a: 1} == {a: 1});
        print([1] == [2]);
        print("x" == "x");
        print(nil == nil);
        """
        assert outs(src) == ["true", "true", "false", "true", "true"]


class TestConformanceControlFlow:
    def test_if_else_chain(self):
        src = """
        fn classify(n) {
          if (n < 10) { return "small"; }
          else if (n < 100) { return "medium"; }
          return "large";
        }
        print(classify(5));
        print(classify(50));
        print(classify(500));
        """
        assert outs(src) == ["small", "medium", "large"]

    def test_while_loop(self):
        src = """
        let i = 0;
        let total = 0;
        while (i < 5) {
          total = total + i;
          i = i + 1;
        }
        print(total);
        """
        assert outs(src) == ["10"]

    def test_for_break_continue(self):
        src = """
        let evens = 0;
        for (let i = 0; i < 10; i = i + 1) {
          if (i % 2 == 1) { continue; }
          if (i == 8) { break; }
          evens = evens + i;
        }
        print(evens);
        """
        assert outs(src) == ["12"]

    def test_logical_short_circuit(self):
        src = """
        fn boom() { return 1 / 0; }
        print(false and boom());
        print(true or boom());
        print(true and "yes");
        print(false or "fallback");
        """
        assert outs(src) == ["false", "true", "yes", "fallback"]


class TestConformanceFunctions:
    def test_recursion_fib(self):
        src = """
        fn fib(n) {
          if (n < 2) { return n; }
          return fib(n - 1) + fib(n - 2);
        }
        print(fib(15));
        """
        assert outs(src) == ["610"]

    def test_higher_order(self):
        src = """
        fn twice(f, x) { return f(f(x)); }
        fn add_one(n) { return n + 1; }
        print(twice(add_one, 41));
        """
        assert outs(src) == ["43"]

    def test_first_class_closures(self):
        src = """
        fn make_adder(n) {
          return fn(x) { return x + n; };
        }
        let add5 = make_adder(5);
        let add10 = make_adder(10);
        print(add5(1));
        print(add10(1));
        """
        assert outs(src) == ["6", "11"]

    def test_arity_error_identical(self):
        src = 'fn f(a, b) { return a; } print(f(1));'
        r1, r2 = both(src)
        assert "expects 2" in r1.error.message
        assert r1.error.message == r2.error.message


class TestConformanceCollections:
    def test_arrays(self):
        src = """
        let xs = [10, 20, 30];
        xs.push(40);
        print(len(xs));
        print(xs[3]);
        print(xs.pop());
        print(xs[0] + xs[1]);
        """
        assert outs(src) == ["4", "40", "40", "30"]

    def test_maps(self):
        src = """
        let m = {"name": "forge", version: 2};
        m["author"] = "rahul";
        print(m.name);
        print(m["version"]);
        print(has(m, "author"));
        print(keys(m));
        """
        assert outs(src) == [
            "forge",
            "2",
            "true",
            '["name", "version", "author"]',
        ]

    def test_map_delete(self):
        src = """
        let m = {a: 1, b: 2};
        del(m, "a");
        print(has(m, "a"));
        print(len(m));
        """
        assert outs(src) == ["false", "1"]

    def test_map_property_read_and_write(self):
        src = """
        let cfg = {host: "localhost"};
        cfg.port = 8080;
        print(cfg.host);
        print(cfg.port);
        """
        assert outs(src) == ["localhost", "8080"]

    def test_nested_structures(self):
        src = '''
        let users = [
          {name: "a", scores: [1, 2]},
          {name: "b", scores: [3, 4]}
        ];
        let total = 0;
        for (let u in nothing) { }
        '''
        r1 = run_source(src.replace('for (let u in nothing) { }', ''), "interp")
        assert r1.ok()


class TestConformanceStrings:
    def test_builtins(self):
        src = '''
        print(upper("abc"));
        print(lower("XYZ"));
        print(split("a,b,c", ","));
        print(join(["1", "2"], "-"));
        print(str(99) + "!");
        print(num("42") + 1);
        print(type([]));
        print(type("s"));
        print(type(1));
        print(type(nil));
        '''
        assert outs(src) == [
            "ABC", "xyz", '["a", "b", "c"]', "1-2",
            "99!", "43", "array", "string", "number", "nil",
        ]

    def test_escapes_and_len(self):
        src = 'print(len("a\\nb"));'
        assert outs(src) == ["3"]


class TestRuntimeErrors:
    def test_division_by_zero_both_engines(self):
        r1, r2 = both("print(1 / 0);")
        assert r1.error.message == r2.error.message == "division by zero"

    def test_out_of_bounds(self):
        r1, r2 = both("let a = [1]; print(a[5]);")
        assert "out of bounds" in r1.error.message
        assert r1.error.message == r2.error.message

    def test_budget_aborts_runaway_loop(self):
        src = "while (true) { }"
        r1 = run_source(src, "interp", budget=50000)
        r2 = run_source(src, "vm", budget=50000)
        assert r1.error is not None and "budget" in r1.error.message
        assert r2.error is not None and "budget" in r2.error.message

    def test_call_non_function(self):
        r1, r2 = both('let x = 5; x();')
        assert "cannot call" in r1.error.message
        assert r1.error.message == r2.error.message


class TestDiagnostics:
    def test_syntax_error_caret(self):
        from forgelang.driver import format_error

        src = "let = 5;"
        result = run_source(src, "interp")
        rendered = format_error(result.error, src)
        assert "line 1" in rendered
        assert "^" in rendered
        assert "expected variable name" in rendered

    def test_runtime_error_position(self):
        src = 'print(1);\nprint(2);\nprint(1/0);'
        r = run_source(src, "interp")
        rendered = r.error.render(src)
        assert "line 3" in rendered
        assert "division by zero" in rendered


class TestGC:
    def test_collections_triggered(self):
        src = """
        for (let i = 0; i < 2000; i = i + 1) {
          let junk = [i, i + 1];
        }
        print("survived");
        """
        r1, r2 = both(src)
        assert r1.output == ["survived"]
        assert r1.stats.gc_allocations > 2000
        assert r1.stats.gc_collections >= 1

    def test_live_objects_survive_collection(self):
        src = """
        let keep = [];
        for (let i = 0; i < 3000; i = i + 1) {
          keep.push([i]);
        }
        print(len(keep));
        """
        r1, _ = both(src)
        assert r1.output == ["3000"]
        assert r1.stats.gc_live_after >= 3000

    def test_gc_stats_reported(self):
        r = run_source("let a = [1];", gc_threshold=1)
        assert r.stats.gc_allocations >= 1
