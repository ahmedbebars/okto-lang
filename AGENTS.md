# Notes for AI coding agents

This file is for AI assistants working **on the Okto compiler** in this repository.
To learn the **Okto language** itself (to write `.ok` programs), read [AI-GUIDE.md](AI-GUIDE.md).

## The project in one paragraph

Okto is a compiler written in Python 3.10+ with no dependencies. A `.ok` file goes through
`okto/lexer.py` → `okto/parser.py` → `okto/checker.py`, then one of two emitters:
`okto/emit_js.py` (JavaScript for Node.js) or `okto/emit_go.py` (Go, built into one native program).
The checker writes facts onto the syntax tree (`e.t` type, `e.want` target type, `e.var`,
`s.vt`) that the emitters read. Both emitters must give exactly the same program output.

## Commands

```bash
python tests/run_tests.py          # language tests on Node and Go (add --node to skip Go)
python tests/test_cli.py           # the okto command and every example
python -m okto run examples/hello.ok
python -m okto check file.ok --json
ruff check . && ruff format --check .
```

## Rules

- Every change to the language needs a test case in `tests/run_tests.py`.
- A new error code goes in `okto/errors.py` with all four texts: English message, English fix,
  Arabic message, Arabic fix.
- A new keyword or built-in needs an Arabic form, and a line in the tables of `AI-GUIDE.md`.
- Keep `AI-GUIDE.md` exactly in step with the compiler. Its examples are in
  `examples/guide_check.ok`, which the tests run.
- The run-time code of both backends is in the `PRELUDE` string at the top of each emitter.
  A change to one backend's run time almost always needs the same change in the other.
- Do not add dependencies to the compiler.
- Files are UTF-8 with LF line endings. Python code uses 4 spaces and single quotes.
