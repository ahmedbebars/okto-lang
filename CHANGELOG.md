# Changelog

All notable changes to Okto are written in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the version is below 1.0, a minor version (0.x) may change the language.

## [Unreleased]

## [0.4.0] - 2026-11-15

The first public release.

### Added

- **Permissions.** `allow read`, `allow write` and `allow env` lines. The checker rejects a program
  that touches a file or an environment value without one (E140), and the run time stops a program
  that leaves the allowed paths, including `..` tricks.
- **The `secret` type**, with `secret_env`, `secret_file`, `secret_equals` (constant time) and `reveal`.
  A secret cannot be printed, written or put inside a text (E141).
- **Safe queries.** `sql("... {value} ...")` keeps values apart from the query text, with
  `sql_text`, `sql_text_numbered` and `sql_values`. A query cannot be built from a changing text (E142).
- `env(name)` to read an environment value.
- `okto --version`, and an installable `okto` command (`pip install`).
- A single-file build of the compiler, `okto.pyz`, attached to each release.
- Tests of the command line and of every example, next to the 148 language tests.

### Changed

- Reading and writing files now need an `allow` line.

## [0.3.0] - 2026-11-15

### Added

- **Go backend.** `okto build file.ok` makes one native program, and `okto run --go` runs through Go.
- Every test program runs on Node and on Go, and both must print the same output.
- Values after the file name reach the program through `args()`.

### Fixed

- Decimal arithmetic gives the same result on both backends (`0.1 + 0.2`).
- A whole number above 2^53 written in the code is rejected (E134) instead of losing precision.
- A list passed to a function, walked by a loop or taken from `??` can no longer be changed
  through another name.

## [0.2.0] - 2026-11-15

### Added

- Records, with named and typed fields.
- Dicts, where a lookup returns an optional value.
- Assignment to a field or an item: `name.field = ...`, `name[i] = ...`.
- Text functions: `split`, `join`, `trim`, `replace`, `find`, `slice`, `upper`, `lower`,
  `starts_with`, `ends_with`.
- List functions: `sort`, `slice`, `contains`.
- Files: `read_file`, `write_file`, `append_file`.

## [0.1.0] - 2026-11-15

### Added

- The core language: `let`, `var`, functions, `if`, `while`, `for`, lists, optional types.
- English and Arabic keywords, Arabic digits and the Arabic comma.
- The checker: types, `none` safety, constants, names, return paths and definition order.
- JavaScript backend for Node.js.
- Errors with a code, a message and a fix line, in English and Arabic, and as JSON.
- The `okto` command: `run`, `check` and `build`.

[Unreleased]: https://github.com/ahmedbebars/okto-lang/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/ahmedbebars/okto-lang/releases/tag/v0.4.0
