"""Builds okto.pyz: the whole compiler in one file that runs with `python okto.pyz`.
Run: python tools/build_pyz.py [output path]   (default: dist/okto.pyz)"""

import os
import shutil
import sys
import tempfile
import zipapp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv):
    out = os.path.abspath(argv[0] if argv else os.path.join(ROOT, 'dist', 'okto.pyz'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    stage = tempfile.mkdtemp(prefix='okto_pyz_')
    try:
        shutil.copytree(
            os.path.join(ROOT, 'okto'), os.path.join(stage, 'okto'), ignore=shutil.ignore_patterns('__pycache__')
        )
        with open(os.path.join(stage, '__main__.py'), 'w', encoding='utf-8', newline='\n') as f:
            f.write('from okto.cli import entry\n\nentry()\n')
        zipapp.create_archive(stage, out, interpreter='/usr/bin/env python3', compressed=True)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    print(out)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
