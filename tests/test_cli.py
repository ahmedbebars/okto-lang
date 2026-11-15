"""Tests of the okto command itself. Run: python tests/test_cli.py
The language is tested in run_tests.py; this file tests what a person types:
the commands, their exit codes, their output, and the example programs.
Options: --node (skip Go), --require-go (fail when Go is missing; used in CI)."""

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from okto import __version__  # noqa: E402
from okto.cli import find_go  # noqa: E402

WITH_GO = find_go() is not None and '--node' not in sys.argv
EXE = '.exe' if os.name == 'nt' else ''


def okto(*args, cwd=ROOT):
    """Runs the okto command. Returns (exit code, stdout, stderr)."""
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONIOENCODING='utf-8')
    env.pop('OKTO_DEMO_PASSWORD', None)
    p = subprocess.run(
        [sys.executable, '-m', 'okto', *list(args)], cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8'
    )
    return p.returncode, p.stdout, p.stderr


def same(got, want):
    assert got == want, 'want %r\n   got  %r' % (want, got)


def test_version():
    same(okto('--version'), (0, 'okto %s\n' % __version__, ''))


def test_usage():
    rc, out, _ = okto()
    same(rc, 2)
    assert 'okto run' in out and __version__ in out, out
    same(okto('run', '--nope', 'examples/hello.ok')[0], 2)


def test_missing_file():
    rc, _, err = okto('run', 'no-such-file.ok')
    same(rc, 2)
    assert 'cannot read no-such-file.ok' in err, err


def test_check_ok():
    same(okto('check', 'examples/hello.ok'), (0, 'ok: no errors\n', ''))
    rc, out, _ = okto('check', 'examples/hello.ok', '--json')
    same((rc, json.loads(out)), (0, {'ok': True, 'file': 'examples/hello.ok', 'errors': []}))


def test_check_errors_as_json():
    rc, out, err = okto('check', '--json', 'examples/mistakes.ok')
    same((rc, err), (1, ''))
    report = json.loads(out)
    same(report['ok'], False)
    same(
        [(e['code'], e['line'], e['col']) for e in report['errors']],
        [('E103', 5, 1), ('E107', 6, 17), ('E101', 7, 7), ('E106', 10, 4), ('E109', 13, 4), ('E102', 17, 14)],
    )
    for e in report['errors']:
        assert e['message'] and e['fix'], e


def test_check_errors_for_people():
    rc, out, err = okto('check', 'examples/mistakes.ok')
    same((rc, out), (1, ''))
    assert 'E103' in err and 'fix:' in err and '6 error(s). Nothing was run.' in err, err
    rc, _, err_ar = okto('check', 'examples/mistakes.ok', '--ar')
    same(rc, 1)
    assert 'E103' in err_ar and err_ar != err, err_ar


def test_run():
    same(okto('run', 'examples/hello.ok'), (0, 'Hello, world!\n2 + 3 = 5\n', ''))
    same(okto('run', 'examples/arabic.ok'), (0, 'المجموع: 225\nممتاز\nالقيمة: 0\n', ''))


def test_nothing_runs_when_the_check_fails():
    rc, out, _ = okto('run', 'examples/mistakes.ok')
    same((rc, out), (1, ''))


def test_values_reach_the_program(work):
    path = os.path.join(work, 'values.ok')
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('print(args())\n')
    same(okto('run', path, 'one', '--json', 'three'), (0, '[one, --json, three]\n', ''))


def test_build_javascript(work):
    out_js = os.path.join(work, 'hello.js')
    same(okto('build', '--js', 'examples/hello.ok', '-o', out_js), (0, out_js + '\n', ''))
    p = subprocess.run(['node', out_js], capture_output=True, text=True, encoding='utf-8')
    same((p.returncode, p.stdout), (0, 'Hello, world!\n2 + 3 = 5\n'))


def test_build_native_program(work):
    exe = os.path.join(work, 'hello' + EXE)
    same(okto('build', 'examples/hello.ok', '-o', exe), (0, exe + '\n', ''))
    p = subprocess.run([exe], capture_output=True, text=True, encoding='utf-8')
    same((p.returncode, p.stdout, p.stderr), (0, 'Hello, world!\n2 + 3 = 5\n', ''))


def test_examples_are_the_same_on_node_and_go(work):
    # A copy, so that the report written by inventory.ok stays out of the project.
    shutil.copytree(os.path.join(ROOT, 'examples'), os.path.join(work, 'examples'))
    runs = [
        ['examples/hello.ok'],
        ['examples/routers.ok'],
        ['examples/arabic.ok'],
        ['examples/guide_check.ok'],
        ['examples/secure.ok'],
        ['examples/inventory.ok', 'examples/routers.csv'],
    ]
    for args in runs:
        on_node = okto('run', *args, cwd=work)
        on_go = okto('run', '--go', *args, cwd=work)
        assert on_node == on_go, '%s differs\n   node: %r\n   go:   %r' % (args[0], on_node, on_go)
        assert on_node[1], '%s printed nothing' % args[0]
    same(on_node[0], 0)
    with open(os.path.join(work, 'examples', 'report.txt'), encoding='utf-8') as f:
        assert f.read().startswith('routers: 5\n')
    rc, _, err = okto('run', 'examples/secure.ok', cwd=work)
    same(rc, 1)
    assert err.startswith('runtime error: line 26: reading the file'), err


TESTS = [
    test_version,
    test_usage,
    test_missing_file,
    test_check_ok,
    test_check_errors_as_json,
    test_check_errors_for_people,
    test_run,
    test_nothing_runs_when_the_check_fails,
    test_values_reach_the_program,
    test_build_javascript,
]
GO_TESTS = [test_build_native_program, test_examples_are_the_same_on_node_and_go]


def main():
    if '--require-go' in sys.argv and find_go() is None:
        print('Go was not found, and --require-go was given.')
        return 2
    failed = 0
    tests = TESTS + (GO_TESTS if WITH_GO else [])
    for test in tests:
        work = tempfile.mkdtemp(prefix='okto_cli_')
        try:
            if test.__code__.co_argcount:
                test(work)
            else:
                test()
        except AssertionError as e:
            failed += 1
            print('FAIL  %s\n   %s' % (test.__name__, e))
        finally:
            shutil.rmtree(work, ignore_errors=True)
    backends = 'node + go' if WITH_GO else 'node only (Go not found)'
    print('%d passed, %d failed  [%s]' % (len(tests) - failed, failed, backends))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
