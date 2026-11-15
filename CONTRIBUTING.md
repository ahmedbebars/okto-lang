# Contributing to Okto

Thank you for helping. Okto is small on purpose, so a good change is usually a small one.

## Ways to help

- **Report a bug.** Open a [bug report](https://github.com/ahmedbebars/okto-lang/issues/new?template=bug_report.yml)
  with the smallest `.ok` program that shows it.
- **Propose a language change.** Open a [language proposal](https://github.com/ahmedbebars/okto-lang/issues/new?template=language_proposal.yml)
  before writing code. A change to the language is discussed first, because every rule must keep
  "one way to do each thing".
- **Improve the documentation or the examples.** These changes can go straight to a pull request.
- **Report a vulnerability** privately, as described in [SECURITY.md](SECURITY.md). Never in a public issue.

## Set up

You need Python 3.10 or newer, Node.js 22 or newer, and Go 1.26 or newer for the native backend.
The compiler has no dependencies.

```bash
git clone https://github.com/ahmedbebars/okto-lang
```

```bash
cd okto-lang
```

```bash
python -m okto run examples/hello.ok
```

## Test

Two test files, both run on Node and on Go:

```bash
python tests/run_tests.py
```

```bash
python tests/test_cli.py
```

- `tests/run_tests.py` holds the language tests: each case is a program and the exact output,
  the error codes, or the run-time error it must give. Add a case for every change.
- `tests/test_cli.py` tests the `okto` command and runs every program in `examples/`.
- Add `--node` to skip Go while you work. The CI runs both backends on Linux, Windows and macOS.

Lint with [Ruff](https://docs.astral.sh/ruff/) (the settings are in `pyproject.toml`):

```bash
ruff check .
```

```bash
ruff format --check .
```

## Rules for a change to the language

1. **Both backends give the same output.** A program must print exactly the same thing on Node and on Go.
2. **Every new error has a code**, an English and an Arabic message, and a `fix` line (`okto/errors.py`).
3. **Every new keyword or built-in has an Arabic form** (`okto/lexer.py`, `okto/checker.py`).
4. **AI-GUIDE.md stays complete.** It is the reference: update it in the same pull request.
   Its examples live in `examples/guide_check.ok`, which the tests run.
5. **No new dependencies** in the compiler.
6. **Write a line in CHANGELOG.md** under `Unreleased`.

## Where things are

| Path | What it does |
|---|---|
| `okto/lexer.py` | Text to tokens, keywords in both languages |
| `okto/parser.py` | Tokens to a syntax tree |
| `okto/checker.py` | Types, `none` safety, constants, permissions. Sets the facts the emitters use |
| `okto/emit_js.py` | Syntax tree to JavaScript, with its run-time code |
| `okto/emit_go.py` | Syntax tree to Go, with its run-time code |
| `okto/errors.py` | Every error code and its messages |
| `okto/cli.py` | The `okto` command |

## Pull requests

- One subject per pull request.
- Write the commit subject in the imperative, in English: `Add sort for records`, not `added sort`.
- The CI must be green. A pull request with a red check is not merged.
- By sending a pull request you agree that your work is published under the [MIT license](LICENSE).

## Code of conduct

Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).
