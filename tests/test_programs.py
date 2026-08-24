from forgelang.driver import assert_conformance


def outs(src):
    return assert_conformance(src)[0].output


def test_nested_closures_three_deep():
    src = """
    fn outer(a) {
      fn middle(b) {
        fn inner(c) { return a + b + c; }
        return inner;
      }
      return middle;
    }
    print(outer(1)(2)(3));
    """
    assert outs(src) == ["6"]


def test_map_filter_reduce_in_language():
    src = """
    fn map(arr, f) {
      let out = [];
      for (let i = 0; i < len(arr); i = i + 1) { out.push(f(arr[i])); }
      return out;
    }
    fn filter(arr, pred) {
      let out = [];
      for (let i = 0; i < len(arr); i = i + 1) {
        if (pred(arr[i])) { out.push(arr[i]); }
      }
      return out;
    }
    fn reduce(arr, f, init) {
      let acc = init;
      for (let i = 0; i < len(arr); i = i + 1) { acc = f(acc, arr[i]); }
      return acc;
    }
    let nums = [1, 2, 3, 4, 5, 6];
    let doubled = map(nums, fn(n) { return n * 2; });
    let evens = filter(nums, fn(n) { return n % 2 == 0; });
    let total = reduce(nums, fn(acc, n) { return acc + n; }, 0);
    print(doubled);
    print(evens);
    print(total);
    """
    assert outs(src) == ["[2, 4, 6, 8, 10, 12]", "[2, 4, 6]", "21"]


def test_fizzbuzz():
    src = """
    for (let i = 1; i <= 15; i = i + 1) {
      if (i % 15 == 0) { print("FizzBuzz"); }
      else if (i % 3 == 0) { print("Fizz"); }
      else if (i % 5 == 0) { print("Buzz"); }
      else { print(i); }
    }
    """
    expected = []
    for i in range(1, 16):
        if i % 15 == 0:
            expected.append("FizzBuzz")
        elif i % 3 == 0:
            expected.append("Fizz")
        elif i % 5 == 0:
            expected.append("Buzz")
        else:
            expected.append(str(i))
    assert outs(src) == expected


def test_mutual_recursion_via_late_binding():
    src = (
        "fn is_even(n) { if (n == 0) { return true; } return is_odd(n - 1); }\n"
        "fn is_odd(n) { if (n == 0) { return false; } return is_even(n - 1); }\n"
        "print(is_even(10));\n"
        "print(is_odd(7));\n"
    )
    assert outs(src) == ["true", "true"]


def test_string_methods_bound():
    src = 'let s = "Forge"; print(s.upper()); print(s.lower()); print(s.len);'
    assert outs(src) == ["FORGE", "forge", "5"]


def test_array_push_pop_semantics():
    src = 'let a = []; print(a.push(9)); print(a.pop());'
    assert outs(src) == ["nil", "9"]


def test_shadowing_in_inner_scope():
    src = (
        'let x = "outer";\n'
        "{\n"
        '  let x = "inner";\n'
        "  print(x);\n"
        "}\n"
        "print(x);\n"
    )
    assert outs(src) == ["inner", "outer"]
