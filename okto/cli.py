"""Okto command line: check, build and run .ok files."""

import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

from . import __version__
from .checker import Checker
from .emit_go import GoEmitter
from .emit_js import Emitter
from .errors import OktoError
from .lexer import tokenize
from .parser import Parser

VERSION = __version__

USAGE = (
    """Okto %s
  okto run   file.ok [values]   check, then run (values reach the program through args())
  okto check file.ok            check only
  okto build file.ok [-o out]   check, then make one native program (needs Go)
  okto --version                print the version
options:
  --go     run through Go instead of Node (slower start, much faster program)
  --js     build a JavaScript file instead of a native program
  --keep   with build: also keep the generated .go file
  --ar     messages in Arabic
  --json   errors as JSON (for tools and AI assistants)
"""
    % VERSION
)

FLAGS = ('--ar', '--json', '--go', '--js', '--keep')
GO_PLACES = (r'C:\Program Files\Go\bin\go.exe', '/usr/local/go/bin/go')


def compile_source(src, target='js'):
    """Returns (generated code or None, list of OktoError)."""
    try:
        ast = Parser(tokenize(src)).program()
    except OktoError as e:
        return None, [e]
    errors = Checker().check(ast)
    if errors:
        return None, errors
    return (GoEmitter() if target == 'go' else Emitter()).program(ast), []


def find_go():
    found = shutil.which('go')
    if found:
        return found
    for p in GO_PLACES:
        if os.path.exists(p):
            return p
    return None


def go_build(code, out_path, keep_dir=None):
    """Compile generated Go code into out_path. Returns (ok, message)."""
    go = find_go()
    if go is None:
        return False, 'Go is needed for this (go.dev/dl). Without it use: okto run file.ok'
    work = keep_dir or tempfile.mkdtemp(prefix='okto_go_')
    try:
        src = os.path.join(work, 'main.go')
        with open(src, 'w', encoding='utf-8', newline='\n') as f:
            f.write(code)
        env = dict(os.environ, GO111MODULE='off', GOFLAGS='')
        p = subprocess.run(
            [go, 'build', '-ldflags=-s -w', '-o', os.path.abspath(out_path), 'main.go'],
            cwd=work,
            env=env,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
        )
        if p.returncode != 0:
            return False, (
                'Okto produced Go code that Go rejected. This is a bug in Okto, not in your program.\n'
                + p.stderr.strip()
            )
        return True, ''
    finally:
        if keep_dir is None:
            shutil.rmtree(work, ignore_errors=True)


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(encoding='utf-8')
    if argv and argv[0] in ('--version', '-V', 'version'):
        print('okto %s' % VERSION)
        return 0
    out_path = None
    if '-o' in argv:
        i = argv.index('-o')
        if i + 1 >= len(argv):
            print(USAGE)
            return 2
        out_path = argv[i + 1]
        argv = argv[:i] + argv[i + 2 :]
    # With "run", flags are read up to the file name and everything after it belongs
    # to the program. With "check" and "build", flags may come anywhere.
    flags, args = set(), []
    for a in argv:
        anywhere = bool(args) and args[0] != 'run'
        if (len(args) < 2 or anywhere) and a in FLAGS:
            flags.add(a)
        elif len(args) < 2 and a.startswith('--'):
            print(USAGE)
            return 2
        else:
            args.append(a)
    lang = 'ar' if '--ar' in flags else 'en'
    as_json = '--json' in flags
    if len(args) < 2 or args[0] not in ('run', 'check', 'build') or (len(args) > 2 and args[0] != 'run'):
        print(USAGE)
        return 2
    cmd, path, program_args = args[0], args[1], args[2:]
    try:
        with open(path, encoding='utf-8-sig') as f:
            src = f.read()
    except OSError as e:
        print('cannot read %s: %s' % (path, e.strerror), file=sys.stderr)
        return 2

    use_go = ('--go' in flags) if cmd == 'run' else ('--js' not in flags)
    code, errors = compile_source(src, 'go' if use_go else 'js')
    if errors:
        if as_json:
            print(
                json.dumps(
                    {'ok': False, 'file': path, 'errors': [e.as_dict(lang) for e in errors]},
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            lines = src.splitlines()
            print('\n\n'.join(e.render(path, lines, lang) for e in errors), file=sys.stderr)
            n = len(errors)
            print(
                ('\n%d error(s). Nothing was run.' if lang == 'en' else '\nعدد الأخطاء: %d. لم يُشغَّل شيء.') % n,
                file=sys.stderr,
            )
        return 1

    if cmd == 'check':
        if as_json:
            print(json.dumps({'ok': True, 'file': path, 'errors': []}))
        else:
            print('ok: no errors' if lang == 'en' else 'تمام: لا توجد أخطاء')
        return 0

    base = os.path.splitext(path)[0]
    if cmd == 'build':
        if not use_go:
            out_path = out_path or base + '.js'
            with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(code)
            print(out_path)
            return 0
        out_path = out_path or base + ('.exe' if os.name == 'nt' else '')
        if '--keep' in flags:
            with open(base + '.go', 'w', encoding='utf-8', newline='\n') as f:
                f.write(code)
        ok, msg = go_build(code, out_path)
        if not ok:
            print(msg, file=sys.stderr)
            return 2
        print(out_path)
        return 0

    work = tempfile.mkdtemp(prefix='okto_run_')
    try:
        if use_go:
            exe = os.path.join(work, 'program.exe' if os.name == 'nt' else 'program')
            ok, msg = go_build(code, exe)
            if not ok:
                print(msg, file=sys.stderr)
                return 2
            return subprocess.run([exe, *program_args]).returncode
        js = os.path.join(work, 'program.js')
        with open(js, 'w', encoding='utf-8', newline='\n') as f:
            f.write(code)
        try:
            return subprocess.run(['node', js, *program_args]).returncode
        except FileNotFoundError:
            print(
                'Node.js is needed for this (nodejs.org). With Go installed use: okto run --go file.ok', file=sys.stderr
            )
            return 2
    finally:
        shutil.rmtree(work, ignore_errors=True)


def entry():
    """Entry point of the installed `okto` command."""
    sys.exit(main(sys.argv[1:]))
