"""Okto checker: finds mistakes before the program runs."""

import difflib

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

    def err(self, code, node, **args):
        self.errors.append(OktoError(code, node.line, node.col, **args))

    # ---- names ------------------------------------------------------
    def find(self, name):
        for sc in reversed(self.scopes):
            if name in sc:
                return sc[name]
        return None

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
            return self.close(name, list(self.fns) + list(self.recs) + EN_BUILTINS) or (
                'define it first: fn %s(): ...' % name,
                'عرّفها أولاً: دالة %s(): ...' % name,
            )
        return self.close(name, [n for sc in self.scopes for n in sc]) or (
            'define it first: let %s = ...' % name,
            'عرّفه أولاً: ثابت %s = ...' % name,
        )

    def taken(self, name):
        """Line where this name is already defined, or None."""
        v = self.find(name)
        if v:
            return v.line
        for table in (self.fns, self.recs):
            if name in table:
                return table[name].line
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
        self.scopes[-1][name] = v

    def check_type(self, t, node):
        """Reports unknown record names and bad dict keys. Returns False when unusable."""
        if not isinstance(t, tuple):
            return True
        if t[0] == 'rec':
            if t[1] not in self.recs:
                self.err('E121', node, name=t[1])
                return False
            return True
        ok = True
        if t[0] == 'dict' and t[1] not in ('text', 'int'):
            self.err('E132', node, got=tstr(t[1]))
            ok = False
        for x in t[1:]:
            ok = self.check_type(x, node) and ok
        return ok

    # ---- program ----------------------------------------------------
    def check(self, ast):
        for s in ast:
            if s.k == 'allow':
                self.allow[s.kind].append(s.value)
        for s in ast:
            if s.k in ('fn', 'record'):
                if norm(s.name) in RESERVED and not getattr(s, 'builtin', False):
                    self.err('E123', s, name=s.name)
                elif self.taken(s.name) is not None:
                    self.err('E104', s, name=s.name, prev=self.taken(s.name))
                else:
                    (self.fns if s.k == 'fn' else self.recs)[s.name] = s
        for s in ast:
            if s.k == 'record':
                seen, fields = {}, []
                for name, t, line, col in s.fields:
                    pos = _Pos(line, col)
                    if name in seen:
                        self.err('E104', pos, name=name, prev=seen[name])
                        continue
                    seen[name] = line
                    fields.append((name, t if self.check_type(t, pos) else 'error', line, col))
                s.fields = fields
            elif s.k == 'fn':
                s.params = [
                    (n, t if self.check_type(t, _Pos(line, col)) else 'error', line, col)
                    for n, t, line, col in s.params
                ]
                if not self.check_type(s.ret, s):
                    s.ret = 'error'
        for s in ast:
            if s.k == 'record':
                self.check_nesting(s)
        for s in ast:
            if s.k not in ('fn', 'record'):
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
                self.check_fn(s)
        self.check_sites()
        self.errors.sort(key=lambda e: (e.line, e.col))
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
        for fn, node, count in self.sites:
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
            if self.check_type(s.ty, s):
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

    def why_fixed(self, name, v):
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
        v = self.find(node.name)
        if v is None:
            self.err(
                'E101',
                node,
                name=node.name,
                hint=self.close(node.name, [n for sc in self.scopes for n in sc])
                or ('define it first: var %s = ...' % node.name, 'عرّفه أولاً: متغير %s = ...' % node.name),
            )
            return None
        if self.cur_fn is not None and v.kind == 'global':
            self.fn_uses[self.cur_fn.name].add(node.name)
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
        s.is_range = it.k == 'call' and self.taken(it.name) is None and BUILTINS.get(norm(it.name)) == 'range'
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
        if k == 'name':
            v = self.find(e.name)
            e.var = v
            if v is None:
                self.err('E101', e, name=e.name, hint=self.suggest(e.name))
                return 'error'
            if self.cur_fn is not None and v.kind == 'global':
                self.fn_uses[self.cur_fn.name].add(e.name)
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
        if e.name in self.recs:
            return self.construct(e, e.name)
        if norm(e.name) in REC_ALIASES and self.taken(e.name) is None:
            return self.construct(e, REC_ALIASES[norm(e.name)])
        if e.named:
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
        if e.name in self.fns:
            f = self.fns[e.name]
            sig = '%s(%s)' % (f.name, ', '.join(p[0] for p in f.params))
            if self.argc(e, len(f.params), sig):
                for a, p in zip(e.args, f.params, strict=True):
                    self.need(a, p[1])
            if self.cur_fn is not None:
                self.fn_calls[self.cur_fn.name].add(f.name)
            else:
                self.sites.append((f.name, e, self.nglobals))
            self.unnarrow_globals()
            return f.ret
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
        f = self.fns.get(h.name) if h.k == 'name' and self.find(h.name) is None else None
        if f is None or len(f.params) != 1 or f.params[0][1] != WEB_REQUEST or f.ret != WEB_RESPONSE:
            self.err('E145', h)
            if h.k != 'name':
                self.val(h)
            return 'void'
        h.t = 'fn'
        e.handler = f
        self.sites.append((f.name, e, self.nglobals))
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
