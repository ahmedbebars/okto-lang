"""Builds the website (GitHub Pages) into one folder.
The site is the files in site/, plus the compiler and the examples, so the
playground runs the very same compiler that is in this repository.
Run: python tools/build_site.py [output folder]   (default: _site)"""

import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from okto import __version__  # noqa: E402

# Examples that work in a browser (no files, no environment values).
PLAYGROUND_EXAMPLES = ['hello.ok', 'routers.ok', 'arabic.ok', 'mistakes.ok', 'secure.ok']


def main(argv):
    out = os.path.abspath(argv[0] if argv else os.path.join(ROOT, '_site'))
    if os.path.exists(out):
        shutil.rmtree(out)
    shutil.copytree(os.path.join(ROOT, 'site'), out)
    shutil.copytree(
        os.path.join(ROOT, 'okto'), os.path.join(out, 'okto'), ignore=shutil.ignore_patterns('__pycache__', '*.pyc')
    )
    modules = sorted(n for n in os.listdir(os.path.join(out, 'okto')) if n.endswith('.py'))
    examples = {}
    for name in PLAYGROUND_EXAMPLES:
        with open(os.path.join(ROOT, 'examples', name), encoding='utf-8') as f:
            examples[name] = f.read()
    manifest = {'version': __version__, 'modules': modules, 'examples': examples}
    with open(os.path.join(out, 'manifest.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    # GitHub Pages must not run Jekyll on this folder.
    open(os.path.join(out, '.nojekyll'), 'w').close()
    print(out)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
