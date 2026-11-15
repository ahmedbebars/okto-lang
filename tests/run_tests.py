"""Okto language tests. Run: python tests/run_tests.py
Every program runs on Node and on Go, and both must print the same thing.
Options: --node (skip Go), --require-go (fail when Go is missing; used in CI).
Each case is (name, source, expected). expected is either the exact program
output (a str), a list of error codes the checker must report, or
('runtime', text) for a program that must stop with that runtime error."""

import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shutil
from concurrent.futures import ThreadPoolExecutor

from okto.cli import compile_source, find_go, go_build
from okto.errors import MSG

WITH_GO = find_go() is not None and '--node' not in sys.argv

CASES = [
    ('arithmetic', 'print(7 // 2, 7 % 3, -7 // 2, -7 % 3, 1 / 2, 2 * 3.5)\n', '3 1 -4 2 0.5 7'),
    ('list copy on assign', 'var a = [1]\nlet b = a\npush(a, 2)\nprint(a, b)\n', '[1, 2] [1]'),
    ('nested list copy', 'var m = [[1]]\nvar r = m[0]\npush(r, 5)\nprint(m, r)\n', '[[1]] [1, 5]'),
    (
        'returned list is a copy',
        'var g = [1]\nfn get() -> list[int]:\n    return g\nvar a = get()\npush(a, 2)\nprint(g, a)\n',
        '[1] [1, 2]',
    ),
    ('narrow lost after assign', 'var x: int? = 5\nif x != none:\n    x = none\n    print(x + 1)\n', ['E106']),
    (
        'narrow lost inside loop',
        'var x: int? = 5\nif x != none:\n    var i = 0\n    while i < 2:\n        print(x + 1)\n'
        '        x = none\n        i = i + 1\n',
        ['E106'],
    ),
    (
        'narrow lost after a call that may change a global',
        'var g: int? = 5\nfn clear():\n    g = none\nif g != none:\n    clear()\n    print(g + 1)\n',
        ['E106'],
    ),
    (
        'narrow after early return',
        'fn f(x: int?) -> int:\n    if x == none:\n        return 0\n    return x + 1\nprint(f(none), f(4))\n',
        '0 5',
    ),
    (
        'narrow not kept when the other branch reassigns',
        'fn f(a: int?) -> int:\n    var x = a\n    if x == none:\n        return 0\n    else:\n        x = none\n'
        '    return x + 1\nprint(f(1))\n',
        ['E106'],
    ),
    ('narrow with and', 'let n = to_int("7")\nif n != none and n > 3:\n    print("big")\n', 'big'),
    ('narrow with not', 'let n = to_int("7")\nif not (n == none):\n    print(n + 1)\n', '8'),
    ('or does not narrow', 'let n = to_int("7")\nif n != none or true:\n    print(n + 1)\n', ['E106']),
    ('global used before it exists', 'fn show():\n    print(limit)\nshow()\nlet limit = 5\n', ['E120']),
    (
        'global used before it exists, through another function',
        'fn a():\n    b()\nfn b():\n    print(limit)\na()\nlet limit = 5\n',
        ['E120'],
    ),
    (
        'function defined after use, mutual recursion',
        'print(is_even(10))\nfn is_even(n: int) -> bool:\n    if n == 0:\n        return true\n    return is_odd(n - 1)\n'
        'fn is_odd(n: int) -> bool:\n    if n == 0:\n        return false\n    return is_even(n - 1)\n',
        'true',
    ),
    ('index outside the list', 'let xs = [1]\nprint(xs[3])\n', ('runtime', 'line 2: index 3')),
    ('division by zero', 'let z = 0\nprint(5 // z)\n', ('runtime', 'line 2: division by zero')),
    ('endless recursion', 'fn f(n: int) -> int:\n    return f(n + 1)\nprint(f(1))\n', ('runtime', 'recursion')),
    ('tab indentation', 'if true:\n\tprint(1)\n', ['E002']),
    ('unclosed text', 'print("abc)\n', ['E004']),
    ('missing colon', 'if true\n    print(1)\n', ['E005']),
    ('bad indentation', 'if true:\n        print(1)\n    print(2)\n', ['E003']),
    ('braces in text', 'print("{{x}} {1 + 2}")\n', '{x} 3'),
    ('escapes', 'print("a\\"b")\n', 'a"b'),
    ('no shadowing', 'let x = 1\nif true:\n    let x = 2\n    print(x)\n', ['E104']),
    ('void result used', 'fn f():\n    print(1)\nlet a = f()\n', ['E113']),
    ('typed list literals', 'let xs: list[float] = [1, 2]\nlet e: list[int] = []\nprint(xs, len(e))\n', '[1, 2] 0'),
    ('untyped empty list', 'let xs = []\n', ['E112']),
    ('loop over a list that grows', 'var xs = [1, 2]\nfor x in xs:\n    push(xs, x)\nprint(len(xs))\n', '4'),
    ('parameters are fixed', 'fn f(xs: list[int]):\n    push(xs, 1)\nf([1])\n', ['E103']),
    ('loop name is fixed', 'for i in range(3):\n    i = 5\n', ['E103']),
    ('none compare on a plain value', 'let x = 1\nif x == none:\n    print(1)\n', ['E116']),
    ('useless ??', 'let x = 1\nprint(x ?? 2)\n', ['E117']),
    (
        'recursion',
        'fn fib(n: int) -> int:\n    if n < 2:\n        return n\n    return fib(n - 1) + fib(n - 2)\nprint(fib(15))\n',
        '610',
    ),
    ('nested function', 'if true:\n    fn f():\n        print(1)\n', ['E122']),
    ('break outside loop', 'break\n', ['E118']),
    ('return outside function', 'return 1\n', ['E110']),
    ('useless expression', '1 + 2\n', ['E119']),
    ('text length in letters', 'print(len("سلام"), len([1, 2, 3]))\n', '4 3'),
    ('elif chain', 'let n = 5\nif n > 10:\n    print("a")\nelif n > 3:\n    print("b")\nelse:\n    print("c")\n', 'b'),
    (
        'else if chain',
        'let n = 1\nif n > 10:\n    print("a")\nelse if n > 3:\n    print("b")\nelse:\n    print("c")\n',
        'c',
    ),
    ('range', 'var t = 0\nfor i in range(2, 5):\n    t = t + i\nprint(t)\n', '9'),
    ('index assign', 'var xs = [1, 2]\nxs[0] = 9\nprint(xs)\n', '[9, 2]'),
    ('index assign on a constant', 'let ys = [1]\nys[0] = 2\n', ['E103']),
    ('unknown function with a hint', 'prnt("x")\n', ['E101']),
    ('optional parameter', 'fn f(a: int?) -> int:\n    return a ?? -1\nprint(f(none), f(3))\n', '-1 3'),
    ('none into a plain type', 'let x: int = none\n', ['E102']),
    ('optional in text', 'let n = to_int("x")\nprint("n = {n}")\n', ['E106']),
    ('wrong argument count', 'fn f(a: int):\n    print(a)\nf(1, 2)\n', ['E105']),
    ('mixed list', 'let xs = [1, "a"]\n', ['E102']),
    ('condition must be bool', 'let n = 1\nif n:\n    print(1)\n', ['E108']),
    ('text plus number', 'let n = 1\nprint("n: " + n)\n', ['E107']),
    ('builtin name taken', 'let print = 1\n', ['E123']),
    ('range outside for', 'let r = range(3)\n', ['E124']),
    ('unknown type', 'let x: string = "a"\n', ['E121']),
    ('missing return', 'fn f(a: int) -> int:\n    if a > 0:\n        return 1\n', ['E109']),
    ('multi-line call', 'print(\n    1,\n    2\n)\n', '1 2'),
    (
        'arabic keywords',
        'دالة ضعف(س: عدد) -> عدد:\n    ارجع س * 2\nمتغير ن = 0\nطالما ن < 3:\n    ن = ن + 1\n'
        'إذا ن == 3 و ليس خطأ:\n    اطبع(ضعف(ن))\n',
        '6',
    ),
    ('arabic digits and list', 'ثابت أرقام = [١، ٢، ٣]\nاطبع(طول(أرقام)، أرقام[٠] + ١٠)\n', '3 11'),
    (
        'names that are JavaScript words',
        'let class = 1\nlet function = 2\nlet console = 3\nprint(class + function + console)\n',
        '6',
    ),
    # ---- v0.2: records ----
    (
        'record basics',
        'record Router:\n    name: text\n    ping: int?\nlet r = Router(name: "core", ping: none)\nprint(r.name, r)\n',
        'core Router(name: core, ping: none)',
    ),
    (
        'record used before its definition',
        'let p = Point(x: 1, y: 2)\nprint(p.x + p.y)\nrecord Point:\n    x: int\n    y: int\n',
        '3',
    ),
    (
        'record is copied on assign',
        'record P:\n    x: int\nvar a = P(x: 1)\nlet b = a\na.x = 5\nprint(a.x, b.x)\n',
        '5 1',
    ),
    ('record field on a constant', 'record P:\n    x: int\nlet a = P(x: 1)\na.x = 5\n', ['E103']),
    ('record missing field', 'record P:\n    x: int\n    y: int\nlet a = P(x: 1)\n', ['E129']),
    ('record unknown field in constructor', 'record P:\n    x: int\nlet a = P(x: 1, z: 2)\n', ['E130']),
    ('record without field names', 'record P:\n    x: int\nlet a = P(1)\n', ['E127']),
    ('record unknown field', 'record P:\n    width: int\nlet a = P(width: 1)\nprint(a.widht)\n', ['E130']),
    ('record wrong field type', 'record P:\n    x: int\nlet a = P(x: "1")\n', ['E102']),
    ('field of a plain value', 'let n = 5\nprint(n.x)\n', ['E130']),
    ('optional field must be checked', 'record R:\n    ping: int?\nlet r = R(ping: 5)\nprint(r.ping + 1)\n', ['E106']),
    (
        'optional field through a name',
        'record R:\n    ping: int?\nlet r = R(ping: 5)\nlet p = r.ping\nif p != none:\n    print(p + 1)\n',
        '6',
    ),
    (
        'nested places',
        'record Site:\n    name: text\n    tags: list[text]\nvar sites = [Site(name: "a", tags: [])]\n'
        'push(sites[0].tags, "main")\nsites[0].name = "b"\nprint(sites)\n',
        '[Site(name: b, tags: [main])]',
    ),
    (
        'loop item is a snapshot',
        'record P:\n    x: int\nvar ps = [P(x: 1), P(x: 2)]\nfor p in ps:\n    ps[0].x = 9\n    print(p.x)\nprint(ps[0].x)\n',
        '1\n2\n9',
    ),
    ('loop item cannot be changed', 'record P:\n    x: int\nlet ps = [P(x: 1)]\nfor p in ps:\n    p.x = 2\n', ['E103']),
    (
        'parameter does not follow a changed global',
        'record P:\n    x: int\nvar g = P(x: 1)\nfn f(p: P):\n    g.x = 7\n    print(p.x, g.x)\nf(g)\n',
        '1 7',
    ),
    (
        'list parameter does not follow a changed global',
        'var g = [1]\nfn f(xs: list[int]):\n    push(g, 2)\n    print(len(xs), len(g))\nf(g)\n',
        '1 2',
    ),
    ('record comparison', 'record P:\n    x: int\nlet a = P(x: 1)\nprint(a == a)\n', ['E107']),
    ('unknown record type', 'fn f(p: Pont):\n    print(1)\n', ['E121']),
    ('record name taken', 'record P:\n    x: int\nlet P = 1\n', ['E104']),
    ('named values to a function', 'fn f(a: int):\n    print(a)\nf(a: 1)\n', ['E127']),
    (
        'arabic record',
        'سجل راوتر:\n    الاسم: نص\n    السرعة: عدد\nثابت ر = راوتر(الاسم: "برج"، السرعة: 40)\nاطبع(ر.الاسم، ر.السرعة)\n',
        'برج 40',
    ),
    # ---- v0.2: dicts ----
    (
        'dict basics',
        'var d = {"a": 1, "b": 2}\nd["c"] = 3\nprint(d, len(d), d["a"] ?? 0, d["zz"] ?? -1)\n',
        '{a: 1, b: 2, c: 3} 3 1 -1',
    ),
    ('dict lookup may be none', 'let d = {"a": 1}\nprint(d["a"] + 1)\n', ['E106']),
    (
        'dict keys, contains, remove',
        'var d: dict[text, int] = {}\nd["x"] = 1\nd["y"] = 2\nremove(d, "x")\nprint(keys(d), contains(d, "x"), contains(d, "y"))\n',
        '[y] false true',
    ),
    (
        'dict counting words',
        'var count: dict[text, int] = {}\nfor w in split("a b a c a", " "):\n    count[w] = (count[w] ?? 0) + 1\n'
        'for k in sort(keys(count)):\n    print(k, count[k] ?? 0)\n',
        'a 3\nb 1\nc 1',
    ),
    ('dict is copied on assign', 'var d = {1: "a"}\nlet e = d\nd[2] = "b"\nprint(len(d), len(e))\n', '2 1'),
    ('dict on a constant', 'let d = {"a": 1}\nd["b"] = 2\n', ['E103']),
    ('dict wrong key type', 'let d = {"a": 1}\nprint(d[1] ?? 0)\n', ['E102']),
    ('dict bad key kind', 'let d: dict[float, int] = {}\n', ['E132']),
    ('untyped empty dict', 'let d = {}\n', ['E112']),
    ('loop over a dict', 'let d = {"a": 1}\nfor k in d:\n    print(k)\n', ['E102']),
    (
        'dict of records',
        'record P:\n    x: int\nvar d: dict[text, P] = {}\nd["a"] = P(x: 1)\nlet p = d["a"]\nif p != none:\n    print(p.x)\n',
        '1',
    ),
    (
        'arabic dict',
        'متغير أسعار: قاموس[نص، عدد] = {}\nأسعار["شاي"] = 5\nاطبع(أسعار["شاي"] ?? 0، يحتوي(أسعار، "قهوة"))\n',
        '5 false',
    ),
    # ---- v0.2: text, lists, files ----
    (
        'text functions',
        'let s = "  Hello World  "\nprint(trim(s), upper(trim(s)), lower("AB"), len(split("a,b,c", ",")))\n'
        'print(join(["x", "y"], "-"), replace("a.b.c", ".", "/"), starts_with("octopus", "oct"), ends_with("a.ok", ".js"))\n'
        'print(find("hello", "ll") ?? -1, find("hello", "z") ?? -1, contains("hello", "ell"), slice("hello", 1, 3))\n',
        'Hello World HELLO WORLD ab 3\nx-y a/b/c true false\n2 -1 true el',
    ),
    (
        'arabic text functions',
        'ثابت ن = "سلام عليكم"\nاطبع(جزء(ن، 0، 4)، ابحث(ن، "عليكم") ?? -1، طول(قسّم(ن، " ")))\n',
        'سلام 5 2',
    ),
    (
        'to_float',
        'print(to_float("2.5") ?? 0.0, to_float("x") ?? -1.0, to_int("12") ?? 0, to_int("1.5") ?? -1)\n',
        '2.5 -1 12 -1',
    ),
    (
        'sort and slice lists',
        'let xs = [3, 1, 2]\nprint(sort(xs), xs, slice(xs, 0, 2), contains(xs, 2), sort(["b", "a"]))\n',
        '[1, 2, 3] [3, 1, 2] [3, 1] true [a, b]',
    ),
    ('slice outside', 'print(slice("abc", 1, 9))\n', ('runtime', 'line 1: slice 1..9')),
    ('sort needs simple items', 'let xs = [[1], [2]]\nprint(sort(xs))\n', ['E102']),
    ('builtin wrong type', 'print(trim(5))\n', ['E102']),
    ('builtin wrong count', 'print(split("a"))\n', ['E105']),
    (
        'missing file is none',
        'allow read "."\nlet t = read_file("no-such-file-okto.txt")\nif t == none:\n    print("missing")\n',
        'missing',
    ),
    ('file content must be checked', 'allow read "."\nlet t = read_file("x.txt")\nprint(len(t))\n', ['E106']),
    ('args is a list of text', 'print(len(args()))\n', '0'),
    # ---- v0.3: cases that are hard for the Go backend ----
    (
        'unused names and unused results',
        'let a = 1\nif true:\n    let b = 2\nfor i in range(2):\n    let c = 3\nlen([1])\n'
        'fn f(x: int) -> int:\n    let d = 4\n    return x\nf(1)\nprint("ok")\n',
        'ok',
    ),
    (
        'int and float mixed',
        'let n = 3\nlet f = 1.5\nlet xs: list[float] = [n, f]\nvar t: float = n\nt = t + n\n'
        'print(n + f, n * f, n < f, n == 3.0, xs, t, [n, f])\n',
        '4.5 4.5 false true [3, 1.5] 6 [3, 1.5]',
    ),
    (
        'optional conversions',
        'let a: int? = 5\nlet b: float? = a\nlet c: float? = 2\nfn f(x: float?) -> float:\n    return x ?? 0\n'
        'print(b ?? 0.0, c ?? 0.0, f(7), f(none), a == 5, a != none, a == to_int("5"), a == to_int("x"))\n',
        '5 2 7 0 true true true false',
    ),
    (
        'record that points to itself through an optional',
        'record Node:\n    value: int\n    next: Node?\nlet a = Node(value: 1, next: none)\nlet b = Node(value: 2, next: a)\n'
        'let n = b.next\nif n != none:\n    print(b.value, n.value, b)\n',
        '2 1 Node(value: 2, next: Node(value: 1, next: none))',
    ),
    ('record that holds itself', 'record Node:\n    value: int\n    next: Node\n', ['E133']),
    ('records that hold each other', 'record A:\n    b: B\nrecord B:\n    a: A\n', ['E133', 'E133']),
    (
        'changing a proven optional record',
        'record P:\n    x: int\nvar p: P? = P(x: 1)\nlet q = p\nif p != none:\n    p.x = 9\n    print(p.x)\nprint(q)\n',
        '9\nP(x: 1)',
    ),
    (
        'float text',
        'print(1000000.0, 0.1 + 0.2, 1 / 3, 2.0 * 2, 7 / 2)\n',
        '1000000 0.30000000000000004 0.3333333333333333 4 3.5',
    ),
    ('names with marks', 'ثابت عَدَد = 5\nاطبع(عَدَد + 1)\n', '6'),
    ('lazy ??', 'fn loud() -> int:\n    print("called")\n    return 1\nlet a: int? = 5\nprint(a ?? loud())\n', '5'),
    (
        'dict with optional values',
        'var d: dict[text, int?] = {"a": none, "b": 2}\nlet a = d["a"]\nlet b = d["b"]\nprint(a == none, b ?? 0, d)\n',
        'true 2 {a: none, b: 2}',
    ),
    (
        'nested dicts and lists copy',
        'var d: dict[text, list[int]] = {"a": [1]}\nlet e = d\nvar xs = d["a"] ?? []\npush(xs, 2)\nd["a"] = xs\nprint(d, e)\n',
        '{a: [1, 2]} {a: [1]}',
    ),
    # ---- v0.4: permissions ----
    ('reading without permission', 'let t = read_file("data/in.txt")\nprint(t ?? "")\n', ['E140']),
    ('writing with only read permission', 'allow read "data"\nprint(write_file("data/o.txt", "x"))\n', ['E140']),
    ('env without permission', 'print(env("OKTO_TEST_KEY") ?? "")\n', ['E140']),
    (
        'reading inside the allowed folder',
        'allow read "data"\nprint(trim(read_file("data/in.txt") ?? "none"))\n',
        'hello\nworld',
    ),
    (
        'reading outside the allowed folder',
        'allow read "data"\nprint(read_file("other/x.txt") ?? "none")\n',
        ('runtime', "line 2: reading the file 'other/x.txt' is not allowed"),
    ),
    (
        'escaping with ..',
        'allow read "data"\nprint(read_file("data/../other/x.txt") ?? "none")\n',
        ('runtime', 'is not allowed'),
    ),
    (
        'folder with a similar name',
        'allow read "data"\nprint(read_file("data2/x.txt") ?? "none")\n',
        ('runtime', 'is not allowed'),
    ),
    ('allow everything', 'allow read "*"\nprint(read_file("other/x.txt") ?? "none")\n', 'other'),
    (
        'writing the allowed file',
        'allow write "data/out.txt"\nprint(write_file("data/out.txt", "x"), append_file("data/out.txt", "y"))\n',
        'true true',
    ),
    (
        'writing another file',
        'allow write "data/out.txt"\nprint(write_file("data/else.txt", "x"))\n',
        ('runtime', "line 2: writing the file 'data/else.txt' is not allowed"),
    ),
    (
        'env allowed by name',
        'allow env "OKTO_TEST_KEY"\nprint(env("OKTO_TEST_KEY") ?? "none", env("OKTO_TEST_KEY") == none)\n',
        'abc123 false',
    ),
    (
        'env with another name',
        'allow env "OKTO_TEST_KEY"\nprint(env("PATH") ?? "none")\n',
        ('runtime', "reading the environment value 'PATH' is not allowed"),
    ),
    ('allow inside a block', 'if true:\n    allow read "data"\n', ['E143']),
    ('unknown permission', 'allow network "x"\n', ['E144']),
    ('arabic permission', 'اسمح قراءة "data"\nاطبع(نظّف(اقرأ_ملف("data/in.txt") ?? ""))\n', 'hello\nworld'),
    # ---- v0.4: secrets ----
    (
        'secret compare and reveal',
        'allow env "OKTO_TEST_KEY"\nlet k = secret_env("OKTO_TEST_KEY")\nif k != none:\n'
        '    print(secret_equals(k, "abc123"), secret_equals(k, "nope"), secret_equals(k, k), len(reveal(k)))\n',
        'true false true 6',
    ),
    ('secret cannot be printed', 'allow env "K"\nlet k = secret_env("K")\nprint(k)\n', ['E141']),
    (
        'secret cannot go inside a text',
        'allow env "K"\nlet k = secret_env("K")\nif k != none:\n    print("key: {k}")\n',
        ['E141'],
    ),
    (
        'secret cannot become text',
        'allow env "K"\nlet k = secret_env("K")\nif k != none:\n    print(to_text(k))\n',
        ['E141'],
    ),
    (
        'secret cannot be compared with ==',
        'allow env "K"\nlet k = secret_env("K")\nif k != none:\n    print(k == "x")\n',
        ['E107'],
    ),
    (
        'secret is not a text',
        'allow env "K"\nallow write "data"\nlet k = secret_env("K")\nif k != none:\n'
        '    print(write_file("data/leak.txt", k))\n',
        ['E102'],
    ),
    (
        'secret inside other values stays hidden',
        'allow read "data"\nrecord U:\n    name: text\n    key: secret\nlet s = secret_file("data/key.txt")\nif s != none:\n'
        '    let u = U(name: "a", key: s)\n    let copy = u\n    print(u, [s], {"k": copy.key}, secret_equals(s, "s3cret"))\n',
        'U(name: a, key: ***) [***] {k: ***} true',
    ),
    # ---- v0.4: safe queries ----
    (
        'query keeps values apart',
        'let name = "x\' or 1=1 --"\nlet age = 30\nlet q = sql("select * from users where name = {name} and age > {age}")\n'
        'print(sql_text(q))\nprint(sql_text_numbered(q))\nprint(sql_values(q))\n',
        "select * from users where name = ? and age > ?\nselect * from users where name = $1 and age > $2\n[x' or 1=1 --, 30]",
    ),
    ('query from a value', 'let t = "select 1"\nlet q = sql(t)\n', ['E142']),
    (
        'query join and none',
        'let lim: int? = none\nvar q = sql("select * from t where a = {1.5}")\nq = q + sql(" and b = {lim} and c = {true}")\n'
        'print(q, sql_values(q))\n',
        'select * from t where a = ? and b = ? and c = ? [1.5, none, true]',
    ),
    ('query plus text', 'let q = sql("select 1") + " or 1=1"\n', ['E107']),
    ('query value must be simple', 'let q = sql("select {[1, 2]}")\n', ['E102']),
    (
        'arabic query',
        'ثابت رقم = 7\nثابت س = استعلام("select * from t where id = {رقم}")\nاطبع(نص_الاستعلام(س)، قيم_الاستعلام(س))\n',
        'select * from t where id = ? [7]',
    ),
    ('number too large', 'let n = 9007199254740993\n', ['E134']),
    ('negative division', 'print(7 // -2, 7 % -3, -7 // -2, 0 - 7 % 3)\n', '-4 -2 3 -1'),
    (
        '?? result is a copy',
        'var a = [1]\nlet o: list[int]? = none\nvar b = o ?? a\npush(b, 2)\nprint(a, b)\n',
        '[1] [1, 2]',
    ),
    (
        'html escapes values',
        'let n = "<b x=\'1\'>&\\""\nlet a = html("<p>{n} {3} {true}</p>")\nlet b = a + html("<div>{a}</div>")\n'
        'print(to_text(b))\nprint(b)\n',
        '<p>&lt;b x=&#39;1&#39;&gt;&amp;&quot; 3 true</p><div><p>&lt;b x=&#39;1&#39;&gt;&amp;&quot; 3 true</p></div>\n'
        '<p>&lt;b x=&#39;1&#39;&gt;&amp;&quot; 3 true</p><div><p>&lt;b x=&#39;1&#39;&gt;&amp;&quot; 3 true</p></div>',
    ),
    (
        'html as a function result',
        'fn card(t: text) -> html:\n    return html("<li>{t}</li>")\nvar page = html("<ul>")\nfor t in ["a", "<b>"]:\n'
        '    page = page + card(t)\nprint(to_text(page + html("</ul>")))\n',
        '<ul><li>a</li><li>&lt;b&gt;</li></ul>',
    ),
    ('html from a value', 'let t = "<b>"\nlet h = html(t)\n', ['E147']),
    ('html plus text', 'let h = html("<b>") + "<i>"\n', ['E107']),
    ('html with an optional value', 'let d = {"a": "b"}\nlet h = html("{d["a"]}")\n', ['E106']),
    ('html with a list', 'let h = html("{[1, 2]}")\n', ['E102']),
    (
        'html with a secret',
        'allow env "K"\nlet k = secret_env("K")\nif k != none:\n    let h = html("{k}")\n',
        ['E141'],
    ),
    (
        'request and response are plain records',
        'fn h(r: Request) -> Response:\n    return Response(status: 201, type: "text/plain", body: r.method + r.path)\n'
        'let q = Request(method: "GET", path: "/a", query: {"x": "1"}, headers: {}, body: "")\nlet res = h(q)\n'
        'print(res.status, res.body, q.query["x"] ?? "-")\n',
        '201 GET/a 1',
    ),
    ('Request is taken', 'record Request:\n    a: int\n', ['E123']),
    (
        'serve needs permission',
        'fn h(r: Request) -> Response:\n    return Response(status: 200, type: "t", body: "")\nserve("127.0.0.1:1", h)\n',
        ['E140'],
    ),
    ('serve needs a handler', 'allow serve "*"\nserve("127.0.0.1:1", 3)\n', ['E145']),
    (
        'serve handler of the wrong shape',
        'allow serve "*"\nfn h(r: text) -> Response:\n    return Response(status: 200, type: "t", body: "")\n'
        'serve("127.0.0.1:1", h)\n',
        ['E145'],
    ),
    (
        'serve is the last line',
        'allow serve "*"\nfn h(r: Request) -> Response:\n    return Response(status: 200, type: "t", body: "")\n'
        'serve("127.0.0.1:1", h)\nprint(1)\n',
        ['E146'],
    ),
    (
        'serve only at the top level',
        'allow serve "*"\nfn h(r: Request) -> Response:\n    return Response(status: 200, type: "t", body: "")\n'
        'if true:\n    serve("127.0.0.1:1", h)\n',
        ['E146'],
    ),
    (
        'serve address not allowed',
        'allow serve "127.0.0.1:9"\nfn h(r: Request) -> Response:\n    return Response(status: 200, type: "t", body: "")\n'
        'serve("127.0.0.1:1", h)\n',
        ('runtime', "line 4: serving on '127.0.0.1:1' is not allowed"),
    ),
    (
        'serve address must be host and port',
        'allow serve "*"\nfn h(r: Request) -> Response:\n    return Response(status: 200, type: "t", body: "")\n'
        'serve("127.0.0.1:70000", h)\n',
        ('runtime', "line 4: the address '127.0.0.1:70000' must look like 127.0.0.1:8080"),
    ),
    (
        'arabic web words',
        'دالة بطاقة(س: نص) -> صفحة_ويب:\n    ارجع صفحة_ويب("<b>{س}</b>")\n'
        'دالة رد(ط: طلب) -> استجابة:\n    ارجع Response(status: 200, type: "t", body: to_text(بطاقة(ط.path)))\n'
        'ثابت ر = رد(Request(method: "GET", path: "<x>", query: {}, headers: {}, body: ""))\nاطبع(ر.body)\n',
        '<b>&lt;x&gt;</b>',
    ),
]


def run_js(js):
    fd, tmp = tempfile.mkstemp(suffix='.js', prefix='okto_test_')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(js)
        p = subprocess.run(['node', tmp], capture_output=True, text=True, encoding='utf-8')
        return p.returncode, p.stdout, p.stderr
    finally:
        os.remove(tmp)


def run_go(code):
    work = tempfile.mkdtemp(prefix='okto_test_go_')
    try:
        exe = os.path.join(work, 'program.exe' if os.name == 'nt' else 'program')
        ok, msg = go_build(code, exe)
        if not ok:
            return 99, '', msg
        p = subprocess.run([exe], capture_output=True, text=True, encoding='utf-8')
        return p.returncode, p.stdout, p.stderr
    finally:
        shutil.rmtree(work, ignore_errors=True)


def judge(want, result):
    rc, out, err = result
    if isinstance(want, tuple):
        return rc == 1 and err.startswith('runtime error: ') and want[1] in err, (rc, err.strip())
    return rc == 0 and out.rstrip('\n') == want, (rc, out.rstrip('\n'), err.strip())


def one(case):
    """Returns a list of failure texts for this case (empty when it passes)."""
    name, src, want = case
    fails = []
    js, errors = compile_source(src)
    for e in errors:  # every message must format in both languages
        e.parts('en')
        e.parts('ar')
        e.render('t.ok', src.splitlines(), 'ar')
    codes = [e.code for e in errors]
    if isinstance(want, list):
        if codes != want:
            fails.append('FAIL  %s\n   want: %r\n   got:  %r' % (name, want, codes or 'compiled without errors'))
        return fails
    if errors:
        return ['FAIL  %s\n   want: %r\n   got:  %r' % (name, want, codes)]
    runs = [('node', run_js(js))]
    if WITH_GO:
        runs.append(('go', run_go(compile_source(src, 'go')[0])))
    for backend, result in runs:
        ok, got = judge(want, result)
        if not ok:
            fails.append('FAIL  %s  [%s]\n   want: %r\n   got:  %r' % (name, backend, want, got))
    return fails


def fixtures():
    """A small folder tree the permission tests run inside."""
    root = tempfile.mkdtemp(prefix='okto_fixtures_')
    for name, text in (
        ('data/in.txt', 'hello\nworld\n'),
        ('data/key.txt', 's3cret\n'),
        ('other/x.txt', 'other'),
        ('data2/x.txt', 'data2'),
    ):
        full = os.path.join(root, name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    os.chdir(root)
    os.environ['OKTO_TEST_KEY'] = 'abc123'
    return root


def main():
    if '--require-go' in sys.argv and find_go() is None:
        print('Go was not found, and --require-go was given.')
        return 2
    for code, m in MSG.items():
        assert len(m) == 4, code
    fixtures()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(one, CASES))
    failed = 0
    for fails in results:
        if fails:
            failed += 1
            print('\n'.join(fails))
    backends = 'node + go' if WITH_GO else 'node only (Go not found)'
    print('%d passed, %d failed  [%s]' % (len(CASES) - failed, failed, backends))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
