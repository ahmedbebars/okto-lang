"""Okto checker: finds mistakes before the program runs."""

import difflib
import re

from .errors import OktoError
from .lexer import norm

BASIC = ('int', 'float', 'text', 'bool')
LIST_TEXT = ('list', 'text')

# Built-ins with fixed parameter types: name -> (parameter types, result type)
SIMPLE = {
    'trim': (('text',), 'text'),
    'upper': (('text',), 'text'),
    'lower': (('text',), 'text'),
    'split': (('text', 'text'), LIST_TEXT),
    'join': ((LIST_TEXT, 'text'), 'text'),
    'starts_with': (('text', 'text'), 'bool'),
    'ends_with': (('text', 'text'), 'bool'),
    'replace': (('text', 'text', 'text'), 'text'),
    'find': (('text', 'text'), ('opt', 'int')),
    'to_int': (('text',), ('opt', 'int')),
    'to_float': (('text',), ('opt', 'float')),
    'read_file': (('text',), ('opt', 'text')),
    'write_file': (('text', 'text'), 'bool'),
    'append_file': (('text', 'text'), 'bool'),
    'args': ((), LIST_TEXT),
    'env': (('text',), ('opt', 'text')),
    'secret_env': (('text',), ('opt', 'secret')),
    'secret_file': (('text',), ('opt', 'secret')),
    'reveal': (('secret',), 'text'),
    'sql_text': (('sql',), 'text'),
    'sql_text_numbered': (('sql',), 'text'),
    'sql_values': (('sql',), ('list', ('opt', 'text'))),
}
# Built-ins that reach outside the program, and the permission each one needs.
PERMS = {
    'read_file': 'read',
    'secret_file': 'read',
    'write_file': 'write',
    'append_file': 'write',
    'env': 'env',
    'secret_env': 'env',
    'serve': 'serve',
}
PERM_TEXT = {
    'read': (('read files', 'قراءة الملفات'), ('allow read "folder"', 'اسمح قراءة "مجلد"')),
    'write': (('write files', 'كتابة الملفات'), ('allow write "folder"', 'اسمح كتابة "مجلد"')),
    'env': (('read environment values', 'قراءة قيم البيئة'), ('allow env "NAME"', 'اسمح بيئة "NAME"')),
    'serve': (
        ('serve web requests', 'استقبال طلبات الويب'),
        ('allow serve "127.0.0.1:8080"', 'اسمح استضافة "127.0.0.1:8080"'),
    ),
}
SQL_PARAM = ('int', 'float', 'text', 'bool')
# The records every program has (okto/parser.py), with their Arabic names.
REC_ALIASES = {'Request': 'Request', 'Response': 'Response', 'طلب': 'Request', 'استجابة': 'Response'}
WEB_REQUEST, WEB_RESPONSE = ('rec', 'Request'), ('rec', 'Response')
SPECIAL_SIG = {
    'len': 'len(list_or_text_or_dict)',
    'push': 'push(list, item)',
    'to_text': 'to_text(value)',
    'range': 'range(start, end)',
    'contains': 'contains(text_or_list_or_dict, item)',
    'slice': 'slice(text_or_list, start, end)',
    'keys': 'keys(dict)',
    'remove': 'remove(dict, key)',
    'sort': 'sort(list)',
    'secret_equals': 'secret_equals(secret, text)',
    'sql': 'sql("select ... where id = {value}")',
    'html': 'html("<p>{value}</p>")',
    'serve': 'serve("127.0.0.1:8080", handle)',
}
AR_BUILTINS = {
    'اطبع': 'print',
    'طول': 'len',
    'مدى': 'range',
    'اضف': 'push',
    'الى_عدد': 'to_int',
    'الى_نص': 'to_text',
    'الى_عشري': 'to_float',
    'نظف': 'trim',
    'حروف_كبيرة': 'upper',
    'حروف_صغيرة': 'lower',
    'قسم': 'split',
    'ادمج': 'join',
    'يبدا_ب': 'starts_with',
    'ينتهي_ب': 'ends_with',
    'استبدل': 'replace',
    'ابحث': 'find',
    'يحتوي': 'contains',
    'جزء': 'slice',
    'مفاتيح': 'keys',
    'احذف': 'remove',
    'رتب': 'sort',
    'اقرا_ملف': 'read_file',
    'اكتب_ملف': 'write_file',
    'الحق_بملف': 'append_file',
    'مدخلات': 'args',
    'بيئة': 'env',
    'سر_من_بيئة': 'secret_env',
    'سر_من_ملف': 'secret_file',
    'اكشف': 'reveal',
    'سر_يساوي': 'secret_equals',
    'استعلام': 'sql',
    'نص_الاستعلام': 'sql_text',
    'نص_الاستعلام_مرقم': 'sql_text_numbered',
    'قيم_الاستعلام': 'sql_values',
    'صفحة_ويب': 'html',
    'استضف': 'serve',
}
EN_BUILTINS = ['print', *list(SPECIAL_SIG), *list(SIMPLE)]
BUILTINS = dict(AR_BUILTINS)
BUILTINS.update((n, n) for n in EN_BUILTINS)
BUILTINS = {norm(k): v for k, v in BUILTINS.items()}
# The built-in record names cannot be reused either.
RESERVED = set(BUILTINS) | {norm(k) for k in REC_ALIASES}


def ident(name):
    """The name used in generated code. 'tools.clean' (a name from the file tools.ok) becomes
    '5_tools_clean': it starts with a digit, so it can never meet a name written in a program."""
    if '.' not in name:
        return name
    mod, item = name.split('.', 1)
    return '%d_%s_%s' % (len(mod), mod, item)


def recs_in(t):
    """The record names inside a type."""
    if isinstance(t, tuple):
        if t[0] == 'rec':
            yield t[1]
        else:
            for x in t[1:]:
                yield from recs_in(x)


def is_opt(t):
    return isinstance(t, tuple) and t[0] == 'opt'


def is_list(t):
    return isinstance(t, tuple) and t[0] == 'list'


def is_dict(t):
    return isinstance(t, tuple) and t[0] == 'dict'


def is_rec(t):
    return isinstance(t, tuple) and t[0] == 'rec'


def is_agg(t):
    """Lists, dicts and records (or an optional one): values that get copied."""
    if is_opt(t):
        t = t[1]
    return isinstance(t, tuple) and t[0] in ('list', 'dict', 'rec')


def bare(t):
    return t[1] if is_opt(t) else t


def num(t):
    return t in ('int', 'float')


def tstr(t):
    if t is None or t == 'error':
        return '?'
    if t == 'void':
        return ('nothing', 'لا شيء')
    if isinstance(t, tuple):
        if t[0] == 'rec':
            return t[1]
        if t[0] == 'list':
            return 'list[%s]' % tstr(t[1])
        if t[0] == 'dict':
            return 'dict[%s, %s]' % (tstr(t[1]), tstr(t[2]))
        return '%s?' % tstr(t[1])
    return t


def sig_of(b):
    if b in SIMPLE:
        return '%s(%s)' % (b, ', '.join(tstr(p) for p in SIMPLE[b][0]))
    return SPECIAL_SIG[b]


def known(t):
    if t is None or t == 'none':
        return False
    if isinstance(t, tuple) and t[0] != 'rec':
        return all(known(x) for x in t[1:])
    return True


def assignable(src, dst):
    if src == dst or src == 'error' or dst == 'error':
        return True
    if is_opt(dst):
        if src == 'none':
            return True
        return assignable(src[1] if is_opt(src) else src, dst[1])
    if src == 'int' and dst == 'float':
        return True
    if is_list(src) and is_list(dst):
        return src[1] is None or src[1] == dst[1]
    if is_dict(src) and is_dict(dst):
        return src[1] is None or src[1:] == dst[1:]
    return False


def assigned(block, out=None):
    """Names that get a new value somewhere inside this block."""
    out = set() if out is None else out
    for s in block:
        if s.k == 'assign' and s.target.k == 'name':
            out.add(s.target.name)
        elif s.k == 'if':
            assigned(s.then, out)
            if s.other:
                assigned(s.other, out)
        elif s.k in ('while', 'for'):
            assigned(s.body, out)
    return out


def exits(block):
    """True when control never continues after this block."""
    if not block:
        return False
    s = block[-1]
    if s.k in ('return', 'break', 'continue'):
        return True
    return s.k == 'if' and s.other is not None and exits(s.then) and exits(s.other)


def returns(block):
    if not block:
        return False
    s = block[-1]
    if s.k == 'return':
        return True
    return s.k == 'if' and s.other is not None and returns(s.then) and returns(s.other)


def root_of(e):
    """The name at the start of a chain like name.field[index]; None for other values."""
    while e.k in ('index', 'field'):
        e = e.obj
    return e if e.k == 'name' else None


class Var:
    __slots__ = ('kind', 'line', 'mutable', 'order', 't')

    def __init__(self, t, mutable, line, kind, order=-1):
        self.t, self.mutable, self.line, self.kind, self.order = t, mutable, line, kind, order


class _Pos:
    def __init__(self, line, col):
        self.line, self.col = line, col


class Checker:
    def __init__(self):
        self.errors = []
        self.scopes = [{}]  # scopes[0] holds the globals
        self.narrow = [{}]  # names proven "not none" in the current blocks
        self.fns = {}
        self.recs = {}
        self.cur_fn = None
        self.loop = 0
        self.fn_uses = {}  # function -> globals it reads or writes
        self.fn_calls = {}  # function -> functions it calls
        self.sites = []  # top-level calls: (function, node, globals defined so far)
        self.nglobals = 0
        self.allow = {'read': [], 'write': [], 'env': [], 'serve': []}
        self.serve_node = None
        self.serve_bad = False
        # A program can have several files. Top-level names of a used file are kept under
        # 'file.name'; inside that file they are written, and shown in messages, as plain 'name'.
        self.mod = None  # the file being checked
        self.prefix = ''  # 'file.' for a used file, '' for the main file
        self.own = None
        self.pub = set()  # full names marked pub

    def err(self, code, node, **args):
        if self.own is not None:
            args = {k: self.plain(v) for k, v in args.items()}
        e = OktoError(code, node.line, node.col, **args)
        if self.mod is not None:
            e.file, e.path = self.mod.index, self.mod.path
        self.errors.append(e)

    def plain(self, v):
        """Message values with this file's own names written the way the file writes them."""
        if isinstance(v, tuple):
            return tuple(self.plain(x) for x in v)
        return self.own.sub('', v) if isinstance(v, str) else v

    # ---- files ------------------------------------------------------
    def enter(self, mod):
        """Makes mod the file being checked. Returns True when the file changed."""
        if mod is self.mod:
            return False
        self.mod = mod
        self.prefix = mod.prefix if mod is not None else ''
        self.own = re.compile(r'(?<![\w.])' + re.escape(self.prefix)) if self.prefix else None
        return True

    def q(self, name):
        """The full name of a top-level name of this file."""
        return name if '.' in name else self.prefix + name

    def used(self, name):
        """The file that this file brought in under that name, or None."""
        if self.mod is None or self.find(name) is not None:
            return None
        return self.mod.uses.get(name)

    def in_reach(self, names):
        """The top-level names of this file among full names, as this file writes them."""
        if not self.prefix:
            return [n for n in names if '.' not in n]
        return [n[len(self.prefix) :] for n in names if n.startswith(self.prefix)]

    def var_names(self):
        files = list(self.mod.uses) if self.mod is not None else []
        return [n for sc in self.scopes[1:] for n in sc] + self.in_reach(self.scopes[0]) + files

    def pub_hint(self, dep, name):
        names = [n[len(dep.prefix) :] for n in sorted(self.pub) if n.startswith(dep.prefix)]
        if not names:
            return (
                'nothing in %s is public: add pub before a definition there' % dep.rel,
                'لا شيء علني في %s: أضف علني قبل تعريف هناك' % dep.rel,
            )
        return self.close(name, names) or (
            'its public names are: %s' % ', '.join(names),
            'أسماؤه العلنية هي: %s' % '، '.join(names),
        )

    def not_public(self, node, dep, full):
        if full not in self.pub:
            self.err('E157', node, name=full[len(dep.prefix) :], file=dep.rel)

    def check_public(self, node, name, types):
        """A public name of a used file must not show a private record of that file."""
        for t in types:
            for rec in recs_in(t):
                if rec.startswith(self.prefix) and rec not in self.pub:
                    self.err('E160', node, name=name, rec=rec)
                    return

    # ---- names ------------------------------------------------------
    def find(self, name):
        for sc in reversed(self.scopes[1:]):
            if name in sc:
                return sc[name]
        return self.scopes[0].get(self.q(name))

    def cur_type(self, name, v):
        for fr in reversed(self.narrow):
            if name in fr:
                return fr[name]
        return v.t

    def unnarrow(self, names):
        for fr in self.narrow:
            for n in names:
                fr.pop(n, None)

    def unnarrow_globals(self):
        for fr in self.narrow:
            for n in list(fr):
                v = self.find(n)
                if v and v.kind == 'global' and v.mutable:
                    del fr[n]

    def close(self, name, pool):
        m = difflib.get_close_matches(name, list(pool), 1, 0.6)
        return ("did you mean '%s'?" % m[0], "هل تقصد '%s'؟" % m[0]) if m else None

    def suggest(self, name, calls=False):
        if calls:
            return self.close(name, self.in_reach(list(self.fns) + list(self.recs)) + EN_BUILTINS) or (
                'define it first: fn %s(): ...' % name,
                'عرّفها أولاً: دالة %s(): ...' % name,
            )
        return self.close(name, self.var_names()) or (
            'define it first: let %s = ...' % name,
            'عرّفه أولاً: ثابت %s = ...' % name,
        )

    def taken(self, name):
        """Line where this name is already defined, or None."""
        v = self.find(name)
        if v:
            return v.line
        for table in (self.fns, self.recs):
            if self.q(name) in table:
                return table[self.q(name)].line
        if self.mod is not None and name in self.mod.uses:
            return self.mod.use_line[name]
        return None

    def declare(self, node, name, t, mutable, kind):
        if norm(name) in RESERVED:
            self.err('E123', node, name=name)
            return
        prev = self.taken(name)
        if prev is not None:
            self.err('E104', node, name=name, prev=prev)
            return
        v = Var(t, mutable, node.line, kind)
        if kind == 'global':
            v.order = self.nglobals
            self.nglobals += 1
            name = self.q(name)
        self.scopes[-1][name] = v

    def rec_name(self, name, node):
        """The full name of the record that a written type names, or None after reporting why not."""
        if '.' in name:
            first, item = name.split('.', 1)
            if self.mod is not None and first == self.mod.name and name in self.recs:
                return name
            dep = self.used(first)
            if dep is None:
                self.err('E121', node, name=name)
            elif name not in self.recs:
                self.err('E158', node, mod=first, name=item, hint=self.pub_hint(dep, item))
            else:
                self.not_public(node, dep, name)
                return name
            return None
        if self.q(name) in self.recs:
            return self.q(name)
        if name in REC_ALIASES and name in self.recs:
            return name
        self.err('E121', node, name=name)
        return None

    def canon(self, t, node):
        """A written type with full record names. Reports unknown records and bad dict keys;
        returns 'error' when the type cannot be used."""
        if not isinstance(t, tuple):
            return t
        if t[0] == 'rec':
            name = self.rec_name(t[1], node)
            return 'error' if name is None else ('rec', name)
        ok = True
        if t[0] == 'dict' and t[1] not in ('text', 'int'):
            self.err('E132', node, got=tstr(t[1]))
            ok = False
        inner = [self.canon(x, node) for x in t[1:]]
        return (t[0], *inner) if ok and 'error' not in inner else 'error'

    # ---- program ----------------------------------------------------
    def check(self, ast):
        for s in ast:
            if s.k == 'allow':
                self.allow[s.kind].append(s.value)
        for s in ast:
            self.enter(getattr(s, 'mod', None))
            if s.k in ('fn', 'record'):
                s.shown = s.name
                if norm(s.name) in RESERVED and not getattr(s, 'builtin', False):
                    self.err('E123', s, name=s.name)
                elif self.taken(s.name) is not None:
                    self.err('E104', s, name=s.name, prev=self.taken(s.name))
                else:
                    s.name = self.q(s.name)
                    (self.fns if s.k == 'fn' else self.recs)[s.name] = s
                    if getattr(s, 'pub', False):
                        self.pub.add(s.name)
        for s in ast:
            self.enter(getattr(s, 'mod', None))
            if s.k == 'record':
                seen, fields = {}, []
                for name, t, line, col in s.fields:
                    pos = _Pos(line, col)
                    if name in seen:
                        self.err('E104', pos, name=name, prev=seen[name])
                        continue
                    seen[name] = line
                    fields.append((name, self.canon(t, pos), line, col))
                s.fields = fields
            elif s.k == 'fn':
                s.params = [(n, self.canon(t, _Pos(line, col)), line, col) for n, t, line, col in s.params]
                s.ret = self.canon(s.ret, s)
        for s in ast:
            self.enter(getattr(s, 'mod', None))
            if s.k == 'record' and self.recs.get(s.name) is s:
                self.check_nesting(s)
            if self.prefix and getattr(s, 'pub', False) and s.k in ('fn', 'record'):
                types = [f[1] for f in s.fields] if s.k == 'record' else [p[1] for p in s.params] + [s.ret]
                self.check_public(s, s.name, types)
        for s in ast:
            if s.k not in ('fn', 'record'):
                if self.enter(getattr(s, 'mod', None)):
                    self.narrow = [{}]  # what one file proved about its names says nothing about another's
                self.stmt(s)
        top = [s for s in ast if s.k not in ('fn', 'record', 'allow')]
        if (
            self.serve_node is not None
            and not self.serve_bad
            and (top[-1].k != 'expr' or top[-1].e is not self.serve_node)
        ):
            self.err('E146', self.serve_node)
        for s in ast:
            if s.k == 'fn' and self.fns.get(s.name) is s:
                self.enter(getattr(s, 'mod', None))
                self.check_fn(s)
        self.check_sites()
        self.errors.sort(key=lambda e: (e.file, e.line, e.col))
        return self.errors

    def check_nesting(self, rec):
        """A record cannot hold itself directly: it would never end."""
        seen, todo = set(), [rec.name]
        while todo:
            for f in self.recs[todo.pop()].fields:
                t = f[1]
                if is_rec(t) and t[1] in self.recs:
                    if t[1] == rec.name:
                        self.err('E133', rec, name=rec.name)
                        return
                    if t[1] not in seen:
                        seen.add(t[1])
                        todo.append(t[1])

    def check_fn(self, f):
        self.cur_fn = f
        self.fn_uses[f.name] = set()
        self.fn_calls[f.name] = set()
        saved, self.narrow = self.narrow, [{}]
        self.scopes.append({})
        for name, t, line, col in f.params:
            self.declare(_Pos(line, col), name, t, False, 'param')
        for s in f.body:
            self.stmt(s)
        self.scopes.pop()
        self.narrow = saved
        if f.ret != 'void' and not returns(f.body):
            self.err('E109', f, name=f.name, ret=tstr(f.ret))
        self.cur_fn = None

    def check_sites(self):
        globs = self.scopes[0]
        for fn, node, count, mod in self.sites:
            self.enter(mod)
            seen, todo, uses = set(), [fn], set()
            while todo:
                f = todo.pop()
                if f in seen:
                    continue
                seen.add(f)
                uses |= self.fn_uses.get(f, set())
                todo.extend(self.fn_calls.get(f, ()))
            late = sorted((globs[g].order, g) for g in uses if g in globs and globs[g].order >= count)
            if late:
                g = late[0][1]
                self.err('E120', node, fn=fn, name=g, at=globs[g].line)

    # ---- statements -------------------------------------------------
    def block(self, body, pre=None, facts=None):
        self.scopes.append(dict(pre or {}))
        self.narrow.append(dict(facts or {}))
        for s in body:
            self.stmt(s)
        self.narrow.pop()
        self.scopes.pop()

    def stmt(self, s):
        getattr(self, 's_' + s.k)(s)

    def s_decl(self, s):
        if s.ty is not None:
            s.ty = self.canon(s.ty, s)
            if s.ty != 'error':
                self.need(s.value, s.ty)
                t = s.ty
            else:
                self.val(s.value)
                t = 'error'
        else:
            t = self.val(s.value)
            if not known(t):
                self.err('E112', s, name=s.name)
                t = 'error'
        kind = 'global' if self.cur_fn is None and len(self.scopes) == 1 else 'local'
        s.vt = t
        self.declare(s, s.name, t, s.mutable, kind)
        s.full = self.q(s.name) if kind == 'global' else s.name
        if kind == 'global' and getattr(s, 'pub', False):
            self.pub.add(s.full)
            if self.prefix:
                self.check_public(s, s.name, [t])

    def why_fixed(self, name, v):
        if '.' in name:
            return (
                'a name from another file cannot be changed from here',
                'اسم من ملف آخر لا يتغير من هنا',
            )
        if v.kind == 'param':
            return (
                'parameters cannot be changed; copy it first: var x = %s' % name,
                'المُدخلات لا تتغير؛ انسخه أولاً: متغير x = %s' % name,
            )
        if v.kind == 'loop':
            return (
                'the loop name cannot be changed; copy it first: var x = %s' % name,
                'اسم عنصر الحلقة لا يتغير؛ انسخه أولاً: متغير x = %s' % name,
            )
        return (
            "define it with 'var %s = ...' if it must change" % name,
            "عرّفه بـ 'متغير %s = ...' لو لازم يتغير" % name,
        )

    def target_var(self, node):
        """The variable behind a name that is about to be changed; reports errors."""
        if getattr(node, 'bad', False):
            return None
        v = self.find(node.name)
        if v is None:
            self.err(
                'E101',
                node,
                name=node.name,
                hint=self.close(node.name, self.var_names())
                or ('define it first: var %s = ...' % node.name, 'عرّفه أولاً: متغير %s = ...' % node.name),
            )
            return None
        node.full = self.q(node.name) if v.kind == 'global' else node.name
        if self.cur_fn is not None and v.kind == 'global':
            self.fn_uses[self.cur_fn.name].add(node.full)
        if not v.mutable:
            self.err('E103', node, name=node.name, hint=self.why_fixed(node.name, v))
            return None
        return v

    def place(self, node):
        """Type of a changeable place: a var name, or a chain of .field / [index] from one.
        Returns None (after reporting) when it cannot be changed."""
        root = root_of(node)
        if root is None:
            self.err('E125', node)
            return None
        if self.target_var(root) is None:
            return None
        return self.val(node)

    def s_assign(self, s):
        tg = s.target
        node = tg
        while node.k in ('index', 'field') and not self.mod_field(node):
            node = node.obj
        if tg.k == 'name':
            v = self.target_var(tg)
            if v is None:
                self.val(s.value)
            else:
                self.need(s.value, v.t)
            self.unnarrow([tg.name])
            return
        ct = self.place(tg.obj)
        if ct is None:
            self.val(s.value)
            return
        if tg.k == 'field':
            self.need(s.value, self.field_type(ct, tg))
        elif is_list(ct):
            self.need(tg.idx, 'int')
            self.need(s.value, ct[1])
        elif is_dict(ct):
            self.need(tg.idx, ct[1])
            self.need(s.value, ct[2])
        else:
            self.val(tg.idx)
            self.val(s.value)
            if is_opt(ct):
                self.err_none(tg.obj)
            elif ct != 'error':
                self.err('E111', tg.obj, got=tstr(ct))

    def s_expr(self, s):
        t = self.ex(s.e)
        if s.e.k != 'call' and t != 'error':
            self.err('E119', s)

    def s_record(self, s):
        pass

    def s_allow(self, s):
        pass

    def s_use(self, s):
        pass

    def no_secret(self, e, t):
        if bare(t) == 'secret':
            self.err('E141', e)

    def cond(self, e):
        t = self.val(e)
        if t not in ('bool', 'error'):
            if is_opt(t):
                self.err_none(e)
            else:
                self.err('E108', e, got=tstr(t))

    def s_if(self, s):
        self.cond(s.cond)
        yes, no = self.facts(s.cond, True), self.facts(s.cond, False)
        self.block(s.then, facts=yes)
        if s.other is not None:
            self.block(s.other, facts=no)
        then_out = exits(s.then)
        other_out = s.other is not None and exits(s.other)
        after, changed = None, set()
        if then_out and not other_out:
            after, changed = no, assigned(s.other or [])
        elif other_out and not then_out:
            after, changed = yes, assigned(s.then)
        if after:
            for name, t in after.items():
                v = self.find(name)
                if name not in changed and v and is_opt(self.cur_type(name, v)):
                    self.narrow[-1][name] = t

    def s_while(self, s):
        self.unnarrow(assigned(s.body))
        self.unnarrow_globals()
        self.cond(s.cond)
        self.loop += 1
        self.block(s.body, facts=self.facts(s.cond, True))
        self.loop -= 1

    def s_for(self, s):
        it = s.it
        s.is_range = (
            it.k == 'call'
            and not getattr(it, 'mod', None)
            and self.taken(it.name) is None
            and BUILTINS.get(norm(it.name)) == 'range'
        )
        if s.is_range:
            if len(it.args) not in (1, 2):
                self.err('E105', it, name=it.name, exp='1-2', got=len(it.args), sig=SPECIAL_SIG['range'])
            for a in it.args:
                self.need(a, 'int')
            elem = 'int'
        else:
            t = self.val(it)
            if is_list(t):
                elem = t[1] if t[1] is not None else 'error'
            else:
                elem = 'error'
                if is_opt(t):
                    self.err_none(it)
                elif is_dict(t):
                    self.err(
                        'E102',
                        it,
                        exp='list',
                        got=tstr(t),
                        hint=('loop over its keys: for k in keys(d):', 'كرّر على المفاتيح: لكل k في مفاتيح(d):'),
                    )
                elif t != 'error':
                    self.err(
                        'E102',
                        it,
                        exp='list',
                        got=tstr(t),
                        hint=('loop over a list, or over range(start, end)', 'كرّر على قائمة، أو على مدى(بداية، نهاية)'),
                    )
        self.unnarrow(assigned(s.body))
        self.unnarrow_globals()
        pre = {}
        if norm(s.name) in RESERVED:
            self.err('E123', s, name=s.name)
        elif self.taken(s.name) is not None:
            self.err('E104', s, name=s.name, prev=self.taken(s.name))
        else:
            pre[s.name] = Var(elem, False, s.line, 'loop')
        self.loop += 1
        self.block(s.body, pre=pre)
        self.loop -= 1

    def s_break(self, s):
        if not self.loop:
            self.err('E118', s, kw=s.kw)

    s_continue = s_break

    def s_return(self, s):
        if self.cur_fn is None:
            self.err('E110', s)
            if s.value is not None:
                self.val(s.value)
            return
        ret = self.cur_fn.ret
        if s.value is None:
            if ret != 'void':
                self.err(
                    'E102',
                    s,
                    exp=tstr(ret),
                    got=tstr('void'),
                    hint=('return a value: return ...', 'أرجع قيمة: ارجع ...'),
                )
        elif ret == 'void':
            self.val(s.value)
            self.err(
                'E102',
                s.value,
                exp=tstr('void'),
                got=tstr(s.value.t),
                hint=('add a return type to the function header: -> type', 'أضف نوع الإرجاع في رأس الدالة: -> النوع'),
            )
        else:
            self.need(s.value, ret)

    # ---- facts: what a condition proves about optional names --------
    def facts(self, c, truth):
        out = {}
        if c.k == 'bin' and c.op in ('==', '!='):
            a, b = c.l, c.r
            if a.k == 'none':
                a, b = b, a
            if a.k == 'name' and b.k == 'none' and (c.op == '!=') == truth:
                v = self.find(a.name)
                if v and is_opt(v.t):
                    out[a.name] = v.t[1]
        elif c.k == 'bin' and ((c.op == 'and' and truth) or (c.op == 'or' and not truth)):
            out.update(self.facts(c.l, truth))
            out.update(self.facts(c.r, truth))
        elif c.k == 'un' and c.op == 'not':
            return self.facts(c.e, not truth)
        return out

    # ---- expressions ------------------------------------------------
    def err_none(self, e):
        if e.k == 'name':
            n = e.name
            self.err(
                'E106',
                e,
                what="'%s'" % n,
                fix=(
                    'check first: if %s != none:   or give a default: %s ?? value' % (n, n),
                    'افحص أولاً: إذا %s != فارغ:   أو أعطِ بديلاً: %s ?? قيمة' % (n, n),
                ),
            )
        else:
            self.err(
                'E106',
                e,
                what=('this value', 'هذه القيمة'),
                fix=(
                    'give a default with: value ?? default   or store it in a name and check: if name != none:',
                    'أعطِ بديلاً: قيمة ?? بديل   أو خزّنها في اسم وافحص: إذا الاسم != فارغ:',
                ),
            )

    def ex(self, e, expect=None):
        e.t = self._ex(e, expect)
        return e.t

    def val(self, e, expect=None):
        t = self.ex(e, expect)
        if t == 'void':
            self.err('E113', e, name=getattr(e, 'name', '?'))
            e.t = t = 'error'
        return t

    def need(self, e, want):
        t = self.val(e, want)
        e.want = want
        if assignable(t, want):
            return t
        if t == 'none':
            self.err(
                'E102',
                e,
                exp=tstr(want),
                got='none',
                hint=(
                    "declare the type with '?' to allow none: %s?" % tstr(want),
                    "عرّف النوع بعلامة '?' للسماح بالفارغ: %s?" % tstr(want),
                ),
            )
        elif is_opt(t) and assignable(t[1], want):
            self.err_none(e)
        else:
            hint = ('change the value, or change the declared type', 'غيّر القيمة أو غيّر النوع المعلن')
            if t == 'text' and want in ('int', 'float'):
                hint = ('convert it: to_int(text) ?? 0', 'حوّله: الى_عدد(النص) ?? 0')
            elif want == 'text':
                hint = (
                    'convert it: to_text(value)   or write it inside a text: "{value}"',
                    'حوّله: الى_نص(القيمة)   أو اكتبه داخل نص: "{القيمة}"',
                )
            if bare(t) == 'secret' and want == 'text':
                hint = (
                    'a secret is not a text: compare it with secret_equals(secret, text), '
                    'or use reveal(secret) where the real value must leave',
                    'السر ليس نصاً: قارنه بـ سر_يساوي(السر، النص)، أو استخدم اكشف(السر) حيث يجب أن تخرج القيمة',
                )
            self.err('E102', e, exp=tstr(want), got=tstr(t), hint=hint)
        return t

    def unify(self, cur, t, node):
        if cur is None or assignable(cur, t):
            return t
        if not assignable(t, cur):
            self.err(
                'E102',
                node,
                exp=tstr(cur),
                got=tstr(t),
                hint=('all items must have the same type', 'كل العناصر يجب أن تكون من نفس النوع'),
            )
        return cur

    def mod_field(self, e):
        """If e is file.name (a public constant of a used file), turns it into that name. Returns True then."""
        if e.k != 'field' or e.obj.k != 'name':
            return False
        dep = self.used(e.obj.name)
        if dep is None:
            return False
        full = dep.prefix + e.name
        e.bad = False
        if full in self.fns or full in self.recs:
            kind = ('a function', 'دالة') if full in self.fns else ('a record', 'سجل')
            self.err(
                'E102',
                e,
                exp=('a value', 'قيمة'),
                got=kind,
                hint=('call it: %s(...)' % full, 'استدعِه: %s(...)' % full),
            )
            e.bad = True
        elif full not in self.scopes[0]:
            self.err('E158', e, mod=dep.name, name=e.name, hint=self.pub_hint(dep, e.name))
            e.bad = True
        else:
            self.not_public(e, dep, full)
        e.k, e.name, e.full = 'name', full, full
        e.var = None
        return True

    def field_type(self, t, e):
        """Type of field e.name on a value of type t; reports errors."""
        if is_rec(t):
            fields = self.recs[t[1]].fields
            for f in fields:
                if f[0] == e.name:
                    return f[1]
            self.err(
                'E130',
                e,
                what=("record '%s'" % t[1], "السجل '%s'" % t[1]),
                name=e.name,
                hint=self.close(e.name, [f[0] for f in fields])
                or (
                    'its fields are: %s' % ', '.join(f[0] for f in fields),
                    'حقوله هي: %s' % '، '.join(f[0] for f in fields),
                ),
            )
        elif is_opt(t):
            self.err_none(e.obj)
        elif t != 'error':
            self.err(
                'E130',
                e,
                what=('a value of type %s' % tstr(t), 'قيمة من النوع %s' % tstr(t)),
                name=e.name,
                hint=('only records have fields', 'الحقول للسجلات فقط'),
            )
        return 'error'

    def _ex(self, e, expect):
        k = e.k
        if k == 'int':
            if e.v > 9007199254740991:
                self.err('E134', e)
                return 'error'
            return 'int'
        if k == 'float':
            return 'float'
        if k == 'bool':
            return 'bool'
        if k == 'none':
            return 'none'
        if k == 'str':
            for p in e.parts:
                if p[0] == 'e':
                    t = self.val(p[1])
                    if bare(t) == 'secret':
                        self.err('E141', p[1])
                    elif is_opt(t) or t == 'none':
                        self.err_none(p[1])
            return 'text'
        if k == 'field' and self.mod_field(e):
            k = 'name'
        if k == 'name':
            if getattr(e, 'bad', False):
                return 'error'
            v = self.find(e.name)
            e.var = v
            if v is None:
                if self.used(e.name) is not None:
                    hint = (
                        "'%s' is a file: write a name from it after a dot, like %s.name" % (e.name, e.name),
                        "'%s' ملف: اكتب اسماً منه بعد نقطة، مثل %s.الاسم" % (e.name, e.name),
                    )
                else:
                    hint = self.suggest(e.name)
                self.err('E101', e, name=e.name, hint=hint)
                return 'error'
            e.full = self.q(e.name) if v.kind == 'global' else e.name
            if self.cur_fn is not None and v.kind == 'global':
                self.fn_uses[self.cur_fn.name].add(e.full)
            return self.cur_type(e.name, v)
        if k == 'un':
            return self.unary(e)
        if k == 'bin':
            return self.binary(e)
        if k == 'call':
            return self.call(e)
        if k == 'field':
            return self.field_type(self.val(e.obj), e)
        if k == 'index':
            t = self.val(e.obj)
            if is_dict(t):
                self.need(e.idx, t[1])
                return t[2] if is_opt(t[2]) else ('opt', t[2])
            self.need(e.idx, 'int')
            if is_list(t):
                return t[1] if t[1] is not None else 'error'
            if is_opt(t):
                self.err_none(e.obj)
            elif t != 'error':
                self.err('E111', e.obj, got=tstr(t))
            return 'error'
        want = expect[1] if is_opt(expect) else expect
        if k == 'list':
            if is_list(want) and want[1] is not None:
                for it in e.items:
                    self.need(it, want[1])
                return want
            cur = None
            for it in e.items:
                cur = self.unify(cur, self.val(it), it)
            for it in e.items:
                it.want = cur
            return ('list', cur)
        if k == 'dict':
            if is_dict(want) and want[1] is not None:
                for key, value in e.items:
                    self.need(key, want[1])
                    self.need(value, want[2])
                return want
            kt = vt = None
            for key, value in e.items:
                kt = self.unify(kt, self.val(key), key)
                vt = self.unify(vt, self.val(value), value)
            if kt not in (None, 'text', 'int', 'error'):
                self.err('E132', e, got=tstr(kt))
                kt = 'error'
            for key, value in e.items:
                key.want, value.want = kt, vt
            return ('dict', kt, vt)
        raise AssertionError(k)

    def unary(self, e):
        t = self.val(e.e)
        if e.op == 'not':
            if t not in ('bool', 'error'):
                self.err(
                    'E107',
                    e,
                    op='not',
                    types=tstr(t),
                    hint=(
                        "'not' needs a bool; compare explicitly, for example: x == 0",
                        "'ليس' يحتاج قيمة منطقية؛ قارن صراحةً، مثال: x == 0",
                    ),
                )
            return 'bool'
        if is_opt(t):
            self.err_none(e.e)
            return 'error'
        if not num(t) and t != 'error':
            self.err('E107', e, op='-', types=tstr(t), hint=("'-' needs a number", "'-' يحتاج رقماً"))
            return 'error'
        return t

    def binary(self, e):
        op = e.op
        if op in ('and', 'or'):
            self.cond(e.l)
            self.narrow.append(self.facts(e.l, op == 'and'))
            self.cond(e.r)
            self.narrow.pop()
            return 'bool'
        if op == '??':
            lt = self.val(e.l)
            if not is_opt(lt):
                if lt != 'error':
                    self.err('E117', e)
                self.val(e.r)
                return lt if lt != 'none' else 'error'
            self.need(e.r, lt[1])
            return lt[1]
        lt, rt = self.val(e.l), self.val(e.r)
        compare = op in ('==', '!=', '<', '>', '<=', '>=')
        if 'error' in (lt, rt):
            return 'bool' if compare else 'error'
        both = ('%s and %s' % (tstr(lt), tstr(rt)), '%s و %s' % (tstr(lt), tstr(rt)))
        if op == '+' and lt == rt and lt in ('sql', 'html'):
            return lt
        if lt != 'none' and rt != 'none':
            if 'secret' in (bare(lt), bare(rt)):
                self.err(
                    'E107',
                    e,
                    op=op,
                    types=both,
                    hint=('compare a secret with secret_equals(secret, text)', 'قارن السر بـ سر_يساوي(السر، النص)'),
                )
                return 'bool' if compare else 'error'
            if 'sql' in (bare(lt), bare(rt)):
                self.err(
                    'E107',
                    e,
                    op=op,
                    types=both,
                    hint=(
                        'queries can only be joined: sql("...") + sql("...")',
                        'الاستعلامات تُضم فقط: استعلام("...") + استعلام("...")',
                    ),
                )
                return 'bool' if compare else 'error'
            if 'html' in (bare(lt), bare(rt)):
                self.err(
                    'E107',
                    e,
                    op=op,
                    types=both,
                    hint=(
                        'html can only be joined with html: html("...") + html("...")',
                        'صفحة الويب تُضم فقط مع صفحة ويب: صفحة_ويب("...") + صفحة_ويب("...")',
                    ),
                )
                return 'bool' if compare else 'error'
        if op in ('==', '!='):
            if lt == 'none' or rt == 'none':
                other = rt if lt == 'none' else lt
                if not is_opt(other) and other != 'none':
                    self.err('E116', e)
            elif is_agg(lt) or is_agg(rt):
                self.err(
                    'E107',
                    e,
                    op=op,
                    types=both,
                    hint=(
                        'comparing whole lists, dicts or records is not supported yet; compare their parts',
                        'مقارنة القوائم والقواميس والسجلات كاملة غير مدعومة بعد؛ قارن أجزاءها',
                    ),
                )
            elif not (assignable(lt, rt) or assignable(rt, lt)):
                self.err(
                    'E107',
                    e,
                    op=op,
                    types=both,
                    hint=('both sides must have the same type', 'الطرفان يجب أن يكونا من نفس النوع'),
                )
            return 'bool'
        for side, t in ((e.l, lt), (e.r, rt)):
            if is_opt(t) or t == 'none':
                self.err_none(side)
                return 'bool' if compare else 'error'
        if compare:
            if not ((num(lt) and num(rt)) or (lt == 'text' and rt == 'text')):
                self.err('E107', e, op=op, types=both, hint=('compare two numbers or two texts', 'قارن رقمين أو نصّين'))
            return 'bool'
        if op == '+' and lt == 'text' and rt == 'text':
            return 'text'
        if op == '+' and 'text' in (lt, rt):
            self.err(
                'E107',
                e,
                op='+',
                types=both,
                hint=('put the value inside the text instead: "total: {x}"', 'ضع القيمة داخل النص: "المجموع: {x}"'),
            )
            return 'error'
        if not (num(lt) and num(rt)):
            self.err('E107', e, op=op, types=both, hint=('this operator needs two numbers', 'هذه العملية تحتاج رقمين'))
            return 'error'
        if op == '/':
            return 'float'
        if op in ('//', '%'):
            if lt != 'int' or rt != 'int':
                self.err(
                    'E107',
                    e,
                    op=op,
                    types=both,
                    hint=(
                        "'%s' needs two int values; use '/' for float division" % op,
                        "'%s' تحتاج عددين صحيحين؛ استخدم '/' للقسمة العشرية" % op,
                    ),
                )
                return 'error'
            return 'int'
        return 'float' if 'float' in (lt, rt) else 'int'

    # ---- calls ------------------------------------------------------
    def argc(self, e, n, sig):
        if len(e.args) != n:
            self.err('E105', e, name=e.name, exp=n, got=len(e.args), sig=sig)
            for a in e.args:
                self.val(a)
            return False
        return True

    def wrong(self, e, t, exp, hint):
        """Report that e (of type t) is not one of the expected kinds."""
        if is_opt(t):
            self.err_none(e)
        elif t != 'error':
            self.err('E102', e, exp=exp, got=tstr(t), hint=hint)

    def construct(self, e, name):
        rec = self.recs[name]
        e.rec = rec
        example = '%s(%s)' % (rec.name, ', '.join('%s: ...' % f[0] for f in rec.fields))
        if e.args:
            self.err(
                'E127',
                e.args[0],
                what=(
                    'write the field name before each value when creating a record',
                    'اكتب اسم الحقل قبل كل قيمة عند إنشاء سجل',
                ),
                hint=('write: ' + example, 'اكتب: ' + example),
            )
            for a in e.args:
                self.val(a)
        fields = {f[0]: f[1] for f in rec.fields}
        seen = {}
        for name, value, line, col in e.named:
            pos = _Pos(line, col)
            if name not in fields:
                self.err(
                    'E130',
                    pos,
                    what=("record '%s'" % rec.name, "السجل '%s'" % rec.name),
                    name=name,
                    hint=self.close(name, fields) or ('write: ' + example, 'اكتب: ' + example),
                )
                self.val(value)
            elif name in seen:
                self.err('E104', pos, name=name, prev=seen[name])
                self.val(value)
            else:
                seen[name] = line
                self.need(value, fields[name])
        if not e.args:
            for f in rec.fields:
                if f[0] not in seen:
                    self.err('E129', e, rec=rec.name, name=f[0])
        return ('rec', rec.name)

    def call(self, e):
        e.builtin = e.rec = None
        if getattr(e, 'mod', None):
            return self.mod_call(e)
        if self.q(e.name) in self.recs:
            return self.construct(e, self.q(e.name))
        if norm(e.name) in REC_ALIASES and self.taken(e.name) is None:
            return self.construct(e, REC_ALIASES[norm(e.name)])
        if e.named:
            return self.no_names(e)
        if self.q(e.name) in self.fns:
            return self.user_call(e, self.fns[self.q(e.name)])
        b = BUILTINS.get(norm(e.name))
        if b is None:
            self.err('E101', e, name=e.name, hint=self.suggest(e.name, calls=True))
            for a in e.args:
                self.val(a)
            return 'error'
        e.builtin = b
        if b in PERMS and not self.allow[PERMS[b]]:
            what, example = PERM_TEXT[PERMS[b]]
            self.err('E140', e, what=what, example=example)
        if b in SIMPLE:
            params, ret = SIMPLE[b]
            if self.argc(e, len(params), sig_of(b)):
                for a, p in zip(e.args, params, strict=True):
                    self.need(a, p)
            return ret
        return getattr(self, 'b_' + b)(e)

    def mod_call(self, e):
        """file.name(...): a function or a record of a used file."""
        dep = self.used(e.mod)
        if dep is None:
            if self.find(e.mod) is None:
                self.err('E101', e.mod_pos, name=e.mod, hint=self.suggest(e.mod))
            else:
                self.err('E161', e, name=e.name)
        else:
            full = dep.prefix + e.name
            if full in self.recs or full in self.fns:
                self.not_public(e, dep, full)
                if full in self.recs:
                    return self.construct(e, full)
                if e.named:
                    return self.no_names(e)
                return self.user_call(e, self.fns[full])
            self.err('E158', e, mod=e.mod, name=e.name, hint=self.pub_hint(dep, e.name))
        for n in e.named:
            self.val(n[1])
        for a in e.args:
            self.val(a)
        return 'error'

    def user_call(self, e, f):
        e.full = f.name
        sig = '%s(%s)' % (f.name, ', '.join(p[0] for p in f.params))
        if self.argc(e, len(f.params), sig):
            for a, p in zip(e.args, f.params, strict=True):
                self.need(a, p[1])
        if self.cur_fn is not None:
            self.fn_calls[self.cur_fn.name].add(f.name)
        else:
            self.sites.append((f.name, e, self.nglobals, self.mod))
        self.unnarrow_globals()
        return f.ret

    def no_names(self, e):
        """A call that puts names before its values, which only records take."""
        self.err(
            'E127',
            _Pos(e.named[0][2], e.named[0][3]),
            what=(
                'names before values are only for creating records',
                'كتابة الاسم قبل القيمة تكون عند إنشاء السجلات فقط',
            ),
            hint=('pass the values only: %s(value, value)' % e.name, 'مرّر القيم فقط: %s(قيمة، قيمة)' % e.name),
        )
        for n in e.named:
            self.val(n[1])
        for a in e.args:
            self.val(a)
        return 'error'

    def b_print(self, e):
        for a in e.args:
            self.no_secret(a, self.val(a))
        return 'void'

    def b_secret_equals(self, e):
        if self.argc(e, 2, sig_of('secret_equals')):
            self.need(e.args[0], 'secret')
            t = self.val(e.args[1])
            if t not in ('text', 'secret'):
                self.wrong(
                    e.args[1],
                    t,
                    'text / secret',
                    ('compare the secret with a text or with another secret', 'قارن السر بنص أو بسر آخر'),
                )
        return 'bool'

    def b_sql(self, e):
        q = e.args[0] if len(e.args) == 1 else None
        if q is None or q.k != 'str':
            self.err('E142', q or e)
            for a in e.args:
                self.val(a)
            return 'sql'
        q.t = 'text'
        for p in q.parts:
            if p[0] == 'e':
                t = self.val(p[1])
                if t != 'none' and bare(t) not in (*SQL_PARAM, 'error'):
                    self.err(
                        'E102',
                        p[1],
                        exp='int / float / text / bool',
                        got=tstr(t),
                        hint=('a query value must be a simple value', 'قيمة الاستعلام يجب أن تكون قيمة بسيطة'),
                    )
        return 'sql'

    def b_html(self, e):
        h = e.args[0] if len(e.args) == 1 else None
        if h is None or h.k != 'str':
            self.err('E147', h or e)
            for a in e.args:
                self.val(a)
            return 'html'
        h.t = 'text'
        for p in h.parts:
            if p[0] != 'e':
                continue
            t = self.val(p[1])
            if bare(t) == 'secret':
                self.err('E141', p[1])
            elif is_opt(t) or t == 'none':
                self.err_none(p[1])
            elif t not in (*SQL_PARAM, 'html', 'error'):
                self.err(
                    'E102',
                    p[1],
                    exp='int / float / text / bool / html',
                    got=tstr(t),
                    hint=(
                        'build the html of a list with a loop: page = page + html("<li>{item}</li>")',
                        'ابنِ صفحة القائمة بحلقة: الصفحة = الصفحة + صفحة_ويب("<li>{العنصر}</li>")',
                    ),
                )
        return 'html'

    def b_serve(self, e):
        if self.cur_fn is not None or len(self.scopes) > 1 or self.serve_node is not None:
            self.err('E146', e)
            self.serve_bad = True
        self.serve_node = e
        e.handler = None
        if not self.argc(e, 2, sig_of('serve')):
            return 'void'
        self.need(e.args[0], 'text')
        h = e.args[1]
        f = None
        if h.k == 'name' and self.find(h.name) is None:
            f = self.fns.get(self.q(h.name))
        elif h.k == 'field' and h.obj.k == 'name' and self.used(h.obj.name) is not None:
            dep = self.used(h.obj.name)
            f = self.fns.get(dep.prefix + h.name)
            if f is not None:
                self.not_public(h, dep, f.name)
                h.k, h.name = 'name', f.name
        if f is None or len(f.params) != 1 or f.params[0][1] != WEB_REQUEST or f.ret != WEB_RESPONSE:
            self.err('E145', h)
            if h.k != 'name':
                self.val(h)
            return 'void'
        h.t = 'fn'
        e.handler = f
        self.sites.append((f.name, e, self.nglobals, self.mod))
        self.unnarrow_globals()
        return 'void'

    def b_range(self, e):
        self.err('E124', e)
        for a in e.args:
            self.val(a)
        return 'error'

    def b_to_text(self, e):
        if self.argc(e, 1, sig_of('to_text')):
            self.no_secret(e.args[0], self.val(e.args[0]))
        return 'text'

    def b_len(self, e):
        if self.argc(e, 1, sig_of('len')):
            t = self.val(e.args[0])
            if not (is_list(t) or is_dict(t) or t == 'text'):
                self.wrong(
                    e.args[0],
                    t,
                    'list / text / dict',
                    ('len works on a list, a text or a dict', 'طول تعمل على قائمة أو نص أو قاموس'),
                )
        return 'int'

    def b_contains(self, e):
        if self.argc(e, 2, sig_of('contains')):
            t = self.val(e.args[0])
            if t == 'text':
                self.need(e.args[1], 'text')
            elif is_dict(t):
                self.need(e.args[1], t[1])
            elif is_list(t) and (t[1] in BASIC or t[1] is None):
                self.need(e.args[1], t[1] or 'error')
            else:
                self.val(e.args[1])
                self.wrong(
                    e.args[0],
                    t,
                    'text / list / dict',
                    (
                        'contains works on a text, a dict, or a list of simple values',
                        'يحتوي تعمل على نص أو قاموس أو قائمة قيم بسيطة',
                    ),
                )
        return 'bool'

    def b_slice(self, e):
        if not self.argc(e, 3, sig_of('slice')):
            return 'error'
        t = self.val(e.args[0])
        self.need(e.args[1], 'int')
        self.need(e.args[2], 'int')
        if t == 'text' or (is_list(t) and t[1] is not None):
            return t
        self.wrong(e.args[0], t, 'text / list', ('slice works on a text or a list', 'جزء تعمل على نص أو قائمة'))
        return 'error'

    def b_keys(self, e):
        if not self.argc(e, 1, sig_of('keys')):
            return 'error'
        t = self.val(e.args[0])
        if is_dict(t) and t[1] is not None:
            return ('list', t[1])
        self.wrong(e.args[0], t, 'dict', ('keys works on a dict', 'مفاتيح تعمل على قاموس'))
        return 'error'

    def b_sort(self, e):
        if not self.argc(e, 1, sig_of('sort')):
            return 'error'
        t = self.val(e.args[0])
        if is_list(t) and t[1] in ('int', 'float', 'text'):
            return t
        self.wrong(
            e.args[0],
            t,
            'list[int] / list[float] / list[text]',
            ('sort works on a list of numbers or texts', 'رتب تعمل على قائمة أرقام أو نصوص'),
        )
        return 'error'

    def b_push(self, e):
        if self.argc(e, 2, sig_of('push')):
            t = self.place(e.args[0])
            if is_list(t):
                self.need(e.args[1], t[1])
            else:
                self.val(e.args[1])
                if t is not None:
                    self.wrong(e.args[0], t, 'list', ('push adds an item to a list', 'أضف تضيف عنصراً إلى قائمة'))
        return 'void'

    def b_remove(self, e):
        if self.argc(e, 2, sig_of('remove')):
            t = self.place(e.args[0])
            if is_dict(t):
                self.need(e.args[1], t[1])
            else:
                self.val(e.args[1])
                if t is not None:
                    self.wrong(e.args[0], t, 'dict', ('remove deletes a key from a dict', 'احذف تحذف مفتاحاً من قاموس'))
        return 'void'
