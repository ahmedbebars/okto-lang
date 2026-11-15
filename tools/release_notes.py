"""Prints the CHANGELOG.md section of one version: the notes of its GitHub release.
Run: python tools/release_notes.py 0.4.0 [output file]
Fails when the version has no section or the section is empty, so CI catches it early."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def notes(version, changelog):
    lines, inside = [], False
    for line in changelog.splitlines():
        if line.startswith('## ['):
            if inside:
                break
            inside = line.startswith('## [%s]' % version)
            continue
        if inside:
            lines.append(line)
    return '\n'.join(lines).strip()


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    with open(os.path.join(ROOT, 'CHANGELOG.md'), encoding='utf-8') as f:
        text = notes(argv[0], f.read())
    if not text:
        print('CHANGELOG.md has no notes for version %s' % argv[0], file=sys.stderr)
        return 1
    if len(argv) > 1:
        with open(argv[1], 'w', encoding='utf-8', newline='\n') as f:
            f.write(text + '\n')
    else:
        print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
