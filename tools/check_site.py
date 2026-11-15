"""Checks the built website: every local link and script points to a file that exists,
and every example in the manifest compiles. Run: python tools/check_site.py _site"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from okto.cli import compile_source  # noqa: E402


def main(argv):
    site = os.path.abspath(argv[0] if argv else os.path.join(ROOT, '_site'))
    problems = []
    with open(os.path.join(site, 'index.html'), encoding='utf-8') as f:
        html = f.read()
    for ref in re.findall(r'(?:href|src)="([^"]+)"', html):
        if ref.startswith(('http://', 'https://', '#', 'data:', 'mailto:')) or ref == './':
            continue
        if not os.path.exists(os.path.join(site, ref.split('#')[0])):
            problems.append('index.html points to a missing file: %s' % ref)
    for script in ('playground.js', 'worker.js'):
        with open(os.path.join(site, script), encoding='utf-8') as f:
            text = f.read()
        for ref in re.findall(r'(?:fetch|Worker)\("([^"+]+)"', text):
            if not os.path.exists(os.path.join(site, ref)):
                problems.append('%s points to a missing file: %s' % (script, ref))
    with open(os.path.join(site, 'manifest.json'), encoding='utf-8') as f:
        manifest = json.load(f)
    for name in manifest['modules']:
        if not os.path.exists(os.path.join(site, 'okto', name)):
            problems.append('manifest lists a missing module: %s' % name)
    for name, source in manifest['examples'].items():
        errors = compile_source(source)[1]
        if errors and name != 'mistakes.ok':
            problems.append('example %s does not compile: %s' % (name, [e.code for e in errors]))
    if not compile_source(manifest['examples']['mistakes.ok'])[1]:
        problems.append('mistakes.ok should show errors but compiles')
    for p in problems:
        print('PROBLEM  ' + p)
    print('%d problem(s) in %s' % (len(problems), site))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
