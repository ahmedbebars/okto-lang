"""Okto loader: reads the main file and every file it brings in with `use`,
and puts them in the order they run (a used file always comes before its user)."""

import difflib
import os
import posixpath
import unicodedata

from .checker import RESERVED
from .errors import OktoError
from .lexer import AR_KEYWORDS, KEYWORDS, norm, tokenize
from .parser import TYPE_ALIASES, Parser, builtin_records

TYPE_WORDS = {'int', 'float', 'text', 'bool', 'list', 'dict', 'secret', 'sql', 'html'}
PATH_HINT = (
    'write a path from this file that ends with .ok, with / between folders: use "lib/tools.ok"',
    'اكتب مساراً من هذا الملف ينتهي بـ .ok وبين المجلدات /: استخدم "lib/tools.ok"',
)
NAME_HINT = (
    'the file name is the name written before the dot (tools.ok gives tools.name), '
    'so it must be a plain name: rename the file',
    'اسم الملف هو الاسم الذي يُكتب قبل النقطة (tools.ok يعطي tools.name)، فيجب أن يكون اسماً عادياً: غيّر اسم الملف',
)
READ_HINT = (
    'check the path: it starts from the folder of the file that holds this line',
    'راجع المسار: يبدأ من مجلد الملف الذي فيه هذا السطر',
)
NO_FILES_HINT = (
    'there are no other files here: use needs files on a computer',
    'لا توجد ملفات أخرى هنا: استخدم تحتاج ملفات على حاسوب',
)
UTF8_HINT = ('save the file as UTF-8 text', 'احفظ الملف نصاً بترميز UTF-8')


class Module:
    """One source file of a program."""

    def __init__(self, key, path, rel, name, index, src):
        self.key = key  # what makes two paths the same file
        self.path = path  # how messages show it (None for a main file with no known path)
        self.rel = rel  # its path from the main file's folder; this is what a built program keeps
        self.name = name  # the name written before the dot; '' for the main file
        self.index = index  # 0 is the main file
        self.lines = src.splitlines()
        self.ast = []
        self.uses = {}  # name -> Module
        self.use_line = {}  # name -> line of its use

    @property
    def prefix(self):
        return self.name + '.' if self.name else ''


class Problem(Exception):
    """A use line that cannot be followed: an error code and its values."""

    def __init__(self, code, **args):
        super().__init__(code)
        self.code, self.args_ = code, args


def did_you_mean(name, pool):
    m = difflib.get_close_matches(name, list(pool), 1, 0.6)
    return ("did you mean '%s'?" % m[0], "هل تقصد '%s'؟" % m[0]) if m else None


class DiskFiles:
    """Files on this computer. A path in a use line starts from the folder of the file that holds it."""

    def __init__(self, main_path):
        self.abs = {}  # module key -> absolute path
        self.main_key = self.key_of(main_path)
        self.abs[self.main_key] = os.path.abspath(main_path)
        self.main_rel = os.path.basename(main_path)

    @staticmethod
    def key_of(path):
        return os.path.normcase(os.path.realpath(path))

    def find(self, mod, rel):
        """Returns (key, shown path, path from the main folder, text) of the file a use line names."""
        folder = os.path.dirname(self.abs[mod.key])
        for part in rel.split('/'):
            if part in ('.', '..'):
                folder = os.path.normpath(os.path.join(folder, part))
                continue
            try:
                names = os.listdir(folder)
            except OSError:
                names = []
            if part not in names:
                # The same spelling everywhere: a path that only works on Windows is refused.
                other = [n for n in names if n.lower() == part.lower()]
                if other:
                    raise Problem(
                        'E152',
                        path=rel,
                        hint=(
                            "it is named '%s' on disk: write it exactly like that" % other[0],
                            "اسمه على القرص '%s': اكتبه هكذا بالضبط" % other[0],
                        ),
                    )
                raise Problem(
                    'E152', path=rel, hint=did_you_mean(part, [n for n in names if n.endswith('.ok')]) or READ_HINT
                )
            folder = os.path.join(folder, part)
        try:
            with open(folder, encoding='utf-8-sig') as f:
                text = f.read()
        except UnicodeDecodeError:
            raise Problem('E152', path=rel, hint=UTF8_HINT) from None
        except OSError:
            raise Problem('E152', path=rel, hint=READ_HINT) from None
        key = self.key_of(folder)
        self.abs.setdefault(key, folder)
        shown = rel if mod.path is None else os.path.normpath(os.path.join(os.path.dirname(mod.path), rel))
        return key, shown.replace('\\', '/'), posixpath.normpath(posixpath.join(posixpath.dirname(mod.rel), rel)), text


class MemFiles:
    """Files given as a dict of path -> text (tests, and places with no disk). Paths start at the main file's folder."""

    main_key = ''
    main_rel = 'main.ok'

    def __init__(self, files):
        self.files = files

    def find(self, mod, rel):
        path = posixpath.normpath(posixpath.join(posixpath.dirname(mod.rel), rel))
        if path not in self.files:
            hint = did_you_mean(path, self.files) or READ_HINT if self.files else NO_FILES_HINT
            raise Problem('E152', path=rel, hint=hint)
        return path, path, path, self.files[path]


def module_name(rel):
    """The name a use line gives: use "lib/tools.ok" gives tools. Raises Problem for a path that cannot be used."""
    parts = rel.split('/')
    if not rel.endswith('.ok') or '\\' in rel or ':' in rel or rel.startswith('/') or '' in parts:
        raise Problem('E151', path=rel, hint=PATH_HINT)
    name = parts[-1][:-3]
    plain = bool(name) and (name[0] == '_' or name[0].isalpha())
    plain = plain and all(c == '_' or c.isalnum() or unicodedata.category(c) == 'Mn' for c in name)
    if not plain:
        raise Problem('E151', path=rel, hint=NAME_HINT)
    word = norm(name)
    if name in KEYWORDS or word in AR_KEYWORDS or word in RESERVED or name in TYPE_WORDS or word in TYPE_ALIASES:
        raise Problem(
            'E151',
            path=rel,
            hint=(
                "'%s' is a word of the language: rename the file" % name,
                "'%s' كلمة من كلمات اللغة: غيّر اسم الملف" % name,
            ),
        )
    return name


def load_program(src, path=None, files=None):
    """Parses the main file and every file it uses.
    Returns (tree, modules, errors): the tree holds every top-level line in running order,
    each one marked with its file (.mod); modules[0] is the main file."""
    source = DiskFiles(path) if path is not None and files is None else MemFiles(files or {})
    main = Module(source.main_key, path, source.main_rel, '', 0, src)
    modules, order, errors = [main], [], []

    def fail(mod, node, code, **args):
        e = OktoError(code, node.line, node.col, **args)
        e.file, e.path = mod.index, mod.path
        errors.append(e)

    def parse(mod, text):
        try:
            mod.ast = Parser(tokenize(text)).program()
        except OktoError as e:
            e.file, e.path = mod.index, mod.path
            errors.append(e)
            return False
        return True

    def visit(mod, stack):
        for s in mod.ast:
            if s.k != 'use':
                continue
            try:
                name = module_name(s.path)
                key, shown, rel, text = source.find(mod, s.path)
            except Problem as p:
                fail(mod, s, p.code, **p.args_)
                continue
            if name in mod.uses:
                fail(mod, s, 'E104', name=name, prev=mod.use_line[name])
                continue
            keys = [m.key for m in stack]
            if key in keys:
                chain = [m.rel for m in stack[keys.index(key) :]] + [rel]
                fail(mod, s, 'E153', chain=' -> '.join(chain))
                continue
            dep = next((m for m in modules if m.key == key), None)
            if dep is None:
                clash = next((m for m in modules if m.name == name), None)
                if clash is not None:
                    fail(mod, s, 'E154', name=name, a=clash.rel, b=rel)
                    continue
                dep = Module(key, shown, rel, name, len(modules), text)
                modules.append(dep)
                if parse(dep, text):
                    visit(dep, [*stack, dep])
            mod.uses[name] = dep
            mod.use_line[name] = s.line
        order.append(mod)

    if not parse(main, src):
        return [], modules, errors
    visit(main, [main])
    for mod in order:
        if mod is main:
            continue
        for s in mod.ast:
            if s.k == 'allow':
                fail(mod, s, 'E156', main=main.rel)
            elif s.k not in ('use', 'fn', 'record', 'decl'):
                fail(mod, s, 'E155')
    if errors:
        errors.sort(key=lambda e: (e.file, e.line, e.col))
        return [], modules, errors
    tree = builtin_records()
    for node in tree:
        node.mod = main
    for mod in order:
        for s in mod.ast:
            s.mod = mod
        tree.extend(mod.ast)
    return tree, modules, []
