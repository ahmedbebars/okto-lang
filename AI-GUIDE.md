# Okto v0.4 — complete guide for AI assistants

This file is the whole language. Read it once and you can write correct Okto.
Okto is strict on purpose: there is **one way** to do each thing, and the checker
rejects a wrong program **before it runs**, with a fix line you can apply directly.

## Workflow for an AI

1. Write the program in a `.ok` file.
2. Run `okto check file.ok --json`.
3. If `ok` is false, apply each error's `fix` at its `line`/`col`, then check again.
4. Run `okto run file.ok [values]` (the values reach the program through `args()`).
5. Ship with `okto build file.ok`: one native program, no runtime needed (uses Go).
   `okto run` uses Node; `okto run --go` uses Go. Both give the same output.

```json
{"ok": false, "file": "a.ok", "errors": [
  {"code": "E106", "line": 10, "col": 4,
   "message": "'ms' may be none here",
   "fix": "check first: if ms != none:   or give a default: ms ?? value"}]}
```

## Syntax in one screen

```
# comment
let limit = 50                  # constant (cannot change)
var total = 0                   # variable (can change)
let names: list[text] = []      # a type is required only when it cannot be inferred

record Router:                  # a record groups named fields
    name: text
    ping: int?

fn average(values: list[int]) -> float:     # parameter types are required
    if len(values) == 0:
        return 0.0
    var sum = 0
    for v in values:
        sum = sum + v
    return sum / len(values)

let r = Router(name: "core", ping: 12)      # field names are required
var count: dict[text, int] = {}
count[r.name] = (count[r.name] ?? 0) + 1

for i in range(0, 10):          # range(n) or range(start, end); end is not included
    if i % 2 == 0:
        continue
    print("odd: {i}")           # {expr} inside a text inserts a value

while total < limit:
    total = total + 1
```

- Blocks: a line ending with `:` then lines indented by **4 spaces**. Tabs are an error.
- One statement per line. A line may continue inside `( )`, `[ ]` or `{ }`.
- `if / elif / else` (`else if` is the same as `elif`), `while`, `for x in list`, `break`, `continue`, `return`.
- Functions and records are defined at the top level only. They may be used before their definition.

## Types

| Type | Values | Notes |
|---|---|---|
| `int` | `42` | whole number, up to 9007199254740991 |
| `float` | `3.5` | an `int` is accepted where a `float` is expected |
| `text` | `"hi {name}"` | escapes: `\n \t \" \\`; literal brace: `{{` and `}}` |
| `bool` | `true`, `false` | conditions must be `bool`; there is no truthiness |
| `list[T]` | `[1, 2, 3]` | all items have the same type |
| `dict[K, V]` | `{"a": 1}` | `K` is `text` or `int`; keeps insertion order |
| record name | `Router(name: "x", ping: none)` | every field must be given, by name |
| `secret` | from `secret_env` / `secret_file` | cannot be printed, compared with `==` or used as text |
| `sql` | `sql("... {value} ...")` | a query whose values are kept apart from its text |
| `T?` | a `T` or `none` | "optional"; see below |

## Operators

| Operator | Works on | Result |
|---|---|---|
| `+ - *` | numbers | `int`, or `float` if either side is `float` |
| `+` | `text + text` | `text` (text + number is an error: use `"{n}"`) |
| `/` | numbers | always `float` |
| `//` `%` | `int`, `int` | `int` (floor division, like Python) |
| `== !=` | same simple types (not whole lists, dicts or records) | `bool` |
| `< > <= >=` | two numbers or two texts | `bool` (cannot be chained) |
| `and or not` | `bool` | `bool` |
| `??` | `T? ?? T` | `T` (the right side is the default when the left is `none`) |
| `list[i]` | `list[T]`, `int` | `T`; outside the list stops the program |
| `dict[key]` | `dict[K, V]`, `K` | **`V?`** — `none` when the key is missing |
| `value.field` | a record | the field's type |

## The rules that make Okto different

1. **No none surprises.** Only a `T?` can hold `none`, and a `T?` cannot be used as a `T`
   until it is proven not none:

   ```
   let ms = to_int(input_text)     # ms is int?
   if ms != none:
       print(ms + 1)               # inside here ms is int
   let safe = ms ?? 0              # or give a default
   ```

   After `if x == none:` followed by `return` / `break` / `continue`, `x` is a plain `T`
   for the rest of the block. `and` keeps the proof: `if x != none and x > 3:`.
   The proof works on **names only**. For a field or a dict lookup, store it first:
   `let p = r.ping` then `if p != none:`.
   The proof is dropped when the name is assigned again, and for global `var`s when any
   function is called.

2. **Constants by default.** `let` names, function parameters and loop names cannot be
   assigned, and nothing inside them can be changed (`push`, `x.field = ...`, `x[i] = ...`
   all need a `var`). Use `var` for anything that changes.

3. **Lists, dicts and records are values.** `let b = a` copies. Two names never share one
   value, so changing one never changes the other. A value passed to a function cannot
   be changed by that function. A `for` loop walks a snapshot of the list.

4. **No shadowing.** A name is defined once: a local or a parameter cannot reuse the name
   of a global, a function or a record.

5. **No silent failures at run time.** An index outside a list, a slice outside the size
   or a division by zero stops the program with `runtime error: line N: ...`.
   Things that can fail normally return an optional instead: `to_int`, `to_float`, `find`,
   `read_file`, `dict[key]`.

6. **No use-before-definition.** Calling a function that reads a global defined on a
   later line is a check-time error (E120).

## Safety features

**Permissions.** A program can touch files and environment values only if it says so at
the top level. Without the line the checker rejects the program (E140). With it, a path
outside the allowed ones stops the program at run time, including `..` tricks.

```
allow read "data"                 # a folder (everything inside it) or one file
allow write "data/report.txt"
allow env "API_KEY"               # one name;  "*" means anything, for all three kinds
```

**Secrets.** `secret_env(name)` and `secret_file(path)` return `secret?`. A secret cannot be
printed, put inside a text, written, or compared with `==` (E141, E102, E107). Inside a
record or list it shows as `***`.

```
let key = secret_env("API_KEY")
if key != none:
    if secret_equals(key, typed_password):     # constant-time; the second value is a text or a secret
        print("welcome")
    let raw = reveal(key)                      # the only way out; use it only where the value must leave
```

**Safe queries.** `sql(...)` takes a text written right there (never a name: E142). Each
`{value}` becomes a separate parameter, so a value can never change the query.

```
var q = sql("select * from users where name = {name}")
q = q + sql(" and age > {min_age}")            # queries can be joined; a text cannot be added
sql_text(q)             # select * from users where name = ? and age > ?
sql_text_numbered(q)    # ... name = $1 and age > $2
sql_values(q)           # list[text?]: the values in order, none for NULL
```

There is no database connection yet: hand `sql_text` and `sql_values` to the driver when one exists.

## Changing things

```
var routers: list[Router] = []
push(routers, Router(name: "core", ping: none))
routers[0].ping = 12            # a chain of .field and [index] that starts at a var
var d: dict[text, list[int]] = {}
d["a"] = [1]
var items = d["a"] ?? []        # a dict lookup is optional, so it cannot be changed in place:
push(items, 2)                  # change a copy,
d["a"] = items                  # then store it back
```

## Built-in functions

| Call | Result | Notes |
|---|---|---|
| `print(a, b, ...)` | nothing | values separated by one space |
| `len(x)` | `int` | items of a list or dict, letters of a text |
| `push(list, item)` | nothing | the list must start at a `var` |
| `remove(dict, key)` | nothing | the dict must start at a `var` |
| `keys(dict)` | `list[K]` | loop over a dict with `for k in keys(d):` |
| `contains(x, item)` | `bool` | part of a text, item of a list of simple values, key of a dict |
| `slice(x, start, end)` | same as `x` | text or list; `end` is not included |
| `sort(list)` | a sorted copy | list of `int`, `float` or `text` |
| `to_text(value)` | `text` | |
| `to_int(text)` | `int?` | `none` when the text is not a whole number |
| `to_float(text)` | `float?` | |
| `trim(t)` `upper(t)` `lower(t)` | `text` | |
| `split(t, separator)` | `list[text]` | an empty separator splits into letters |
| `join(list_of_text, separator)` | `text` | |
| `replace(t, old, new)` | `text` | replaces every occurrence |
| `starts_with(t, part)` `ends_with(t, part)` | `bool` | |
| `find(t, part)` | `int?` | position of the first occurrence, or `none` |
| `read_file(path)` | `text?` | `none` when the file cannot be read; needs `allow read` |
| `write_file(path, t)` `append_file(path, t)` | `bool` | `false` when it fails; needs `allow write` |
| `env(name)` | `text?` | needs `allow env` |
| `secret_env(name)` `secret_file(path)` | `secret?` | need `allow env` / `allow read` |
| `secret_equals(secret, text)` | `bool` | |
| `reveal(secret)` | `text` | |
| `sql("...")` | `sql` | |
| `sql_text(q)` `sql_text_numbered(q)` | `text` | |
| `sql_values(q)` | `list[text?]` | |
| `args()` | `list[text]` | values given after the file name on the command line |
| `range(start, end)` | — | only as the source of a `for` loop |

There are no methods: write `trim(s)`, never `s.trim()`.

## Arabic keywords

Every keyword has an Arabic form. Both forms can be mixed in one file. Hamza and
diacritics are optional (`إذا` = `اذا`). The Arabic comma `،` and Arabic digits `٠-٩` work.

| English | Arabic | English | Arabic |
|---|---|---|---|
| `let` | `ثابت` | `and` | `و` |
| `var` | `متغير` | `or` | `أو` |
| `fn` | `دالة` | `not` | `ليس` |
| `record` | `سجل` | `true` | `صح` |
| `return` | `ارجع` | `false` | `خطأ` |
| `if` | `إذا` (or `لو`) | `none` | `فارغ` |
| `else` | `وإلا` | `break` | `توقف` |
| `else if` | `وإلا إذا` | `continue` | `استمر` |
| `while` | `طالما` | `in` | `في` |
| `for` | `لكل` | `allow` | `اسمح` |
| `read` | `قراءة` | `write` | `كتابة` |
| `env` | `بيئة` | | |
| `int` | `عدد` | `float` | `عشري` |
| `text` | `نص` | `bool` | `منطقي` |
| `list` | `قائمة` | `dict` | `قاموس` |
| `secret` | `سر` | `sql` | `استعلام` |
| `print` | `اطبع` | `len` | `طول` |
| `range` | `مدى` | `push` | `أضف` |
| `remove` | `احذف` | `keys` | `مفاتيح` |
| `contains` | `يحتوي` | `slice` | `جزء` |
| `sort` | `رتّب` | `to_text` | `إلى_نص` |
| `to_int` | `إلى_عدد` | `to_float` | `إلى_عشري` |
| `trim` | `نظّف` | `upper` | `حروف_كبيرة` |
| `lower` | `حروف_صغيرة` | `split` | `قسّم` |
| `join` | `ادمج` | `replace` | `استبدل` |
| `starts_with` | `يبدأ_ب` | `ends_with` | `ينتهي_ب` |
| `find` | `ابحث` | `read_file` | `اقرأ_ملف` |
| `write_file` | `اكتب_ملف` | `append_file` | `ألحق_بملف` |
| `args` | `مدخلات` | `reveal` | `اكشف` |
| `secret_env` | `سر_من_بيئة` | `secret_file` | `سر_من_ملف` |
| `secret_equals` | `سر_يساوي` | `sql_values` | `قيم_الاستعلام` |
| `sql_text` | `نص_الاستعلام` | `sql_text_numbered` | `نص_الاستعلام_مرقم` |

## Error codes

| Code | Meaning |
|---|---|
| E001–E006 | spelling of the file: bad character, tab, indentation, unclosed text, unexpected word, unclosed `{` |
| E101 | unknown name (with "did you mean") |
| E102 | wrong type |
| E103 | changing a constant, parameter or loop name (or something inside it) |
| E104 | name already defined |
| E105 | wrong number of arguments |
| E106 | value may be none |
| E107 | operator does not fit these types |
| E108 | condition is not bool |
| E109 | function may end without returning |
| E110, E118 | `return` / `break` / `continue` in the wrong place |
| E111 | indexing something that is not a list or a dict |
| E112 | type cannot be inferred (for example `let xs = []` or `let d = {}`) |
| E113 | using the result of a function that returns nothing |
| E116, E117 | useless none check / useless `??` |
| E119 | expression that does nothing |
| E120 | function called before a global it needs is defined |
| E121–E125 | unknown type, nested function or record, built-in name reused, `range` outside `for`, bad assignment target |
| E127 | field names missing when creating a record, or given to a function |
| E129, E130 | record field missing / record has no such field |
| E132 | dict key type is not `text` or `int` |
| E133 | a record holds itself directly (make the field optional or a list) |
| E134 | whole number too large |
| E140 | file or environment access without an `allow` line |
| E141 | a secret shown or turned into text |
| E142 | `sql(...)` given a value instead of a text written in place |
| E143, E144 | `allow` inside a block / unknown permission kind |

## Not in v0.4 yet (do not use)

Modules and imports, methods (`x.y()`), error values, concurrency, lambdas, classes,
network and database access, reading keyboard input, sorting records.
Results of int maths above 2^53 differ between the Node and Go backends.
