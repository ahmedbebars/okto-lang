# The design of Okto

This document explains what Okto is for, why each rule exists, what is built,
what is not, and where the language is honest about its limits.

## Goals

1. **Easy to read and write**, like Python.
2. **Catches the mistake before the program runs**, like Rust, without Rust's difficulty.
3. **Hard to attack**: whole families of vulnerabilities are removed by the language.
4. **Comfortable for AI assistants**: few rules, one way to do each thing, and errors that carry the fix.
5. **Works with existing projects**: it compiles to widely used targets (JavaScript and Go).
6. **Bilingual**: every keyword has an English form and an Arabic form.

## Decisions and their reasons

| Decision | Reason |
|---|---|
| Blocks by indentation (4 spaces) | Easier to read, fewer symbols |
| Types are inferred | You write a type only when it is needed |
| `let` (constant) is the default, `var` only when needed | Most bugs come from a change nobody intended |
| `none` exists only inside a type marked `?` | Removes the most common cause of crashes |
| Lists, dicts and records are copied on assignment | Two names never share one value, so there is no hidden change |
| A name cannot be defined twice in one function | One name has one meaning |
| A condition must be a real `bool` | No surprises like `"0"` and `[]` in other languages |
| A text cannot be added to a number | Write the number inside the text: `"total: {x}"` |
| Every error has a code, a message and a `fix` line | A beginner and an AI can both repair the program directly |
| Errors are available as JSON | Any tool or assistant can read them |
| No methods: `trim(s)`, never `s.trim()` | One call syntax, nothing to guess |
| No `eval`, no reflection | Code is what is written in the file, nothing else |

## What is built

### 0.1: the core

- Lexer: English and Arabic keywords, Arabic digits, the Arabic comma.
- Checker: types, `none` safety, constants, names, return paths, definition order.
- JavaScript emitter that runs on Node.js.
- Run-time errors with a line number: index outside a list, division by zero, endless recursion.
- Command line: `run`, `check` and `build`, with `--ar` and `--json`.

### 0.2: data

- Records: named, typed fields, created by naming every field.
- Dicts: a lookup returns an optional value, so a missing key is never a surprise.
- Changing parts: `name.field = ...` and `name[i].field = ...`, only when the chain starts at a `var`.
- Records and dicts are copied on assignment like lists, and a loop walks a snapshot.
- Text functions (split, join, trim, replace, find, slice, upper, lower) and list functions (sort, slice, contains).
- Files: read, write, append, and command-line values.

### 0.3: native programs

- Go emitter: the same program becomes one native file (about 2 MB) that needs nothing installed.
- `okto build` makes the native program, and `okto run --go` runs through Go.
- The same output on Node and Go: every test runs on both and the results are compared.

### 0.4: safety

- **Permissions.** A program reads a file, writes a file or reads an environment value only with an
  `allow` line at the top of the file. Without the line the checker rejects the program. With it,
  a path outside the allowed ones stops the program at run time, including `..` tricks and
  folders with a similar name.
- **The `secret` type.** A value that cannot be printed, put inside a text, written to a file or
  compared with `==`. It is compared with a constant-time function and leaves only through an
  explicit `reveal`. Inside a record or a list it shows as `***`.
- **Safe queries.** The `sql` type takes its text from the source code only, and the values inside
  `{ }` are kept apart. A query cannot be built from a changing text, and a text cannot be added to a query.

## Roadmap

| Stage | Content |
|---|---|
| 0.5 | Several files (imports), and using Go and JavaScript libraries |
| 0.6 | Errors as values (in place of exceptions), and running tasks at the same time |
| 0.7 | Network and database access, behind an `allow network` permission |
| 0.8 | Tools: a formatter, an editor extension, an MCP server for AI assistants |

The order can change. Proposals are welcome as
[language proposals](https://github.com/ahmedbebars/okto-lang/issues/new/choose).

## Safety: what is done and what is not

**Done:** file and environment permissions, the `secret` type, safe queries, and no `eval` in the language at all.

**Not done yet:**

- Permissions cover the whole program, not each library (there are no libraries yet).
- A program declares its own permissions. They protect against bugs and hostile input,
  not against a hostile author. Read the `allow` lines of a program before you run it.
- Safe queries build the text and the values only. There is no database connection yet.
- Signed libraries with locked versions.
- A secret stays in memory as plain text and is not wiped after use.
- `reveal()` is an escape hatch: once a secret is revealed it is an ordinary text.
- Bypassing permissions through symbolic links is handled in the code but has no automatic test yet.

**A clear limit:** the language removes families of vulnerabilities. It does not remove mistakes
in a program's logic or in a server's configuration.

## Known limits of the current version

- A whole number written in the code is limited to 2^53. A result above that differs between Node and Go.
- On simple arithmetic the Go backend is close to Node. The real difference is in file size,
  ease of shipping and start-up time.
- Run-time error messages are in English only.
- Comparing two whole lists, dicts or records with `==` is not supported.
- The `none` check works on names only. A field or a dict item is stored in a name first, then checked.
- A list of records cannot be sorted yet (it needs functions passed as values).
- Copying lists on assignment costs time with very large lists.
- The first Go build on a machine is slow (the Go standard library is compiled once and cached).
- The compiler is written in Python, so writing Okto needs Python. Running a built program needs nothing.

## What a language needs to spread

AI assistants recommend the languages they have seen a lot of code in. So:

1. `AI-GUIDE.md` teaches any assistant the whole language in one reading.
2. The language is used in a real project first.
3. It is open source, with many examples.
4. Adoption takes years, not months.
