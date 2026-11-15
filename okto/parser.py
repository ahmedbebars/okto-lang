"""Okto parser: tokens -> tree."""

from .errors import OktoError
from .lexer import norm, tokenize

TYPE_ALIASES = {
    'عدد': 'int',
    'عشري': 'float',
    'نص': 'text',
    'منطقي': 'bool',
    'قائمة': 'list',
    'قاموس': 'dict',
    'سر': 'secret',
    'استعلام': 'sql',
}
ALLOW_KINDS = {'read': 'read', 'write': 'write', 'env': 'env', 'قراءة': 'read', 'كتابة': 'write', 'بيئة': 'env'}

SHOW = {
    'NEWLINE': ('the end of the line', 'نهاية السطر'),
    'INDENT': ('an indented line', 'سطر مُزاح'),
    'DEDENT': ('the end of the block', 'نهاية القسم'),
    'EOF': ('the end of the file', 'نهاية الملف'),
    'NAME': ('a name', 'اسم'),
    'INT': ('a number', 'رقم'),
    'FLOAT': ('a number', 'رقم'),
    'STR': ('a text', 'نص'),
    'EXPR': ('a value', 'قيمة'),
}
DEFAULT_FIX = ('check this line', 'راجع هذا السطر')


def show(kind):
    return SHOW.get(kind, ("'%s'" % kind, "'%s'" % kind))


def show_tok(tok):
    if tok.kind == 'NAME' or tok.kind not in SHOW:
        return ("'%s'" % tok.val, "'%s'" % tok.val)
    return SHOW[tok.kind]


class N:
    """A tree node. k is the kind; other fields depend on the kind."""

    def __init__(self, k, line, col, **kw):
        self.k, self.line, self.col = k, line, col
        self.t = None
        self.__dict__.update(kw)


class Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i]

    def at(self, kind):
        return self.t[self.i].kind == kind

    def eat(self, kind, fix=None):
        tok = self.t[self.i]
        if tok.kind != kind:
            raise OktoError('E005', tok.line, tok.col, exp=show(kind), got=show_tok(tok), fix=fix or DEFAULT_FIX)
        self.i += 1
        return tok

    def end(self):
        self.eat('NEWLINE', ('put each statement on its own line', 'ضع كل أمر في سطر مستقل'))

    # ---- statements -------------------------------------------------
    def program(self):
        body = []
        while not self.at('EOF'):
            body.append(self.stmt(True))
        return body

    def block(self):
        self.eat(':', ("add ':' at the end of the line", "أضف ':' في نهاية السطر"))
        self.eat('NEWLINE', ('start the block on a new line', 'ابدأ القسم في سطر جديد'))
        self.eat('INDENT', ('indent the block with 4 spaces', 'أزح القسم 4 مسافات'))
        body = []
        while not self.at('DEDENT'):
            body.append(self.stmt(False))
        self.eat('DEDENT')
        return body

    def stmt(self, top):
        tok = self.peek()
        k = tok.kind
        if k in ('let', 'var'):
            self.i += 1
            name = self.eat('NAME', ('write a name after let/var', 'اكتب اسماً بعد ثابت/متغير'))
            ty = None
            if self.at(':'):
                self.i += 1
                ty = self.type()
            self.eat('=', ('give it a value: let x = 0', 'أعطه قيمة: ثابت x = 0'))
            value = self.expr()
            self.end()
            return N('decl', name.line, name.col, name=name.val, mutable=(k == 'var'), ty=ty, value=value)
        if k == 'fn':
            if not top:
                raise OktoError('E122', tok.line, tok.col)
            self.i += 1
            name = self.eat('NAME', ('write the function name', 'اكتب اسم الدالة'))
            self.eat('(', ("add '(' after the function name", "أضف '(' بعد اسم الدالة"))
            params = []
            while not self.at(')'):
                p = self.eat('NAME')
                self.eat(':', ('every parameter needs a type: name: text', 'كل مُدخل يحتاج نوعاً: الاسم: نص'))
                params.append((p.val, self.type(), p.line, p.col))
                if not self.at(')'):
                    self.eat(',')
            self.eat(')')
            ret = 'void'
            if self.at('->'):
                self.i += 1
                ret = self.type()
            body = self.block()
            return N('fn', name.line, name.col, name=name.val, params=params, ret=ret, body=body)
        if k == 'allow':
            if not top:
                raise OktoError('E143', tok.line, tok.col)
            self.i += 1
            fix = ('write: allow read "folder"   (or write, or env)', 'اكتب: اسمح قراءة "مجلد"   (أو كتابة، أو بيئة)')
            kind = self.eat('NAME', fix)
            if norm(kind.val) not in ALLOW_KINDS:
                raise OktoError('E144', kind.line, kind.col, name=kind.val)
            what = self.eat('STR', fix)
            if len(what.val) != 1 or what.val[0][0] != 's' or not what.val[0][1]:
                raise OktoError(
                    'E005',
                    what.line,
                    what.col,
                    exp=('a plain text', 'نص عادي'),
                    got=('a text with {values}', 'نص فيه {قيم}'),
                    fix=fix,
                )
            self.end()
            return N('allow', tok.line, tok.col, kind=ALLOW_KINDS[norm(kind.val)], value=what.val[0][1])
        if k == 'record':
            if not top:
                raise OktoError('E122', tok.line, tok.col)
            self.i += 1
            name = self.eat('NAME', ('write the record name', 'اكتب اسم السجل'))
            self.eat(':', ("add ':' after the record name", "أضف ':' بعد اسم السجل"))
            self.eat('NEWLINE')
            self.eat(
                'INDENT',
                ('write the fields indented by 4 spaces: name: text', 'اكتب الحقول بإزاحة 4 مسافات: الاسم: نص'),
            )
            fields = []
            while not self.at('DEDENT'):
                f = self.eat('NAME', ('write a field: name: text', 'اكتب حقلاً: الاسم: نص'))
                self.eat(':', ('every field needs a type: name: text', 'كل حقل يحتاج نوعاً: الاسم: نص'))
                fields.append((f.val, self.type(), f.line, f.col))
                self.end()
            self.eat('DEDENT')
            return N('record', name.line, name.col, name=name.val, fields=fields)
        if k == 'return':
            self.i += 1
            value = None if self.at('NEWLINE') else self.expr()
            self.end()
            return N('return', tok.line, tok.col, value=value)
        if k in ('if', 'elif'):
            return self.if_stmt()
        if k == 'while':
            self.i += 1
            cond = self.expr()
            return N('while', tok.line, tok.col, cond=cond, body=self.block())
        if k == 'for':
            self.i += 1
            name = self.eat('NAME', ('write the loop name: for x in items:', 'اكتب اسم العنصر: لكل x في القائمة:'))
            self.eat('in', ("write 'in' after the name: for x in items:", "اكتب 'في' بعد الاسم: لكل x في القائمة:"))
            it = self.expr()
            return N('for', name.line, name.col, name=name.val, it=it, body=self.block())
        if k in ('break', 'continue'):
            self.i += 1
            self.end()
            return N(k, tok.line, tok.col, kw=tok.val)
        e = self.expr()
        if self.at('='):
            self.i += 1
            value = self.expr()
            self.end()
            if e.k not in ('name', 'index', 'field'):
                raise OktoError('E125', e.line, e.col)
            return N('assign', e.line, e.col, target=e, value=value)
        self.end()
        return N('expr', e.line, e.col, e=e)

    def if_stmt(self):
        tok = self.peek()
        self.i += 1
        cond = self.expr()
        then = self.block()
        other = None
        if self.at('elif'):
            other = [self.if_stmt()]
        elif self.at('else'):
            self.i += 1
            other = [self.if_stmt()] if self.at('if') else self.block()
        return N('if', tok.line, tok.col, cond=cond, then=then, other=other)

    def type(self):
        tok = self.eat('NAME', ('write a type such as int, text or list[int]', 'اكتب نوعاً مثل عدد أو نص أو قائمة[عدد]'))
        name = TYPE_ALIASES.get(norm(tok.val), tok.val)
        if name == 'list':
            self.eat('[', ('write the item type: list[int]', 'اكتب نوع العناصر: قائمة[عدد]'))
            t = ('list', self.type())
            self.eat(']')
        elif name == 'dict':
            fix = ('write the key and value types: dict[text, int]', 'اكتب نوع المفتاح والقيمة: قاموس[نص، عدد]')
            self.eat('[', fix)
            kt = self.type()
            self.eat(',', fix)
            t = ('dict', kt, self.type())
            self.eat(']')
        elif name in ('int', 'float', 'text', 'bool', 'secret', 'sql'):
            t = name
        else:
            t = ('rec', tok.val)
        if self.at('?'):
            self.i += 1
            t = ('opt', t)
        return t

    # ---- expressions ------------------------------------------------
    def expr(self):
        left = self.or_()
        while self.at('??'):
            tok = self.eat('??')
            left = N('bin', tok.line, tok.col, op='??', l=left, r=self.or_())
        return left

    def or_(self):
        left = self.and_()
        while self.at('or'):
            tok = self.eat('or')
            left = N('bin', tok.line, tok.col, op='or', l=left, r=self.and_())
        return left

    def and_(self):
        left = self.not_()
        while self.at('and'):
            tok = self.eat('and')
            left = N('bin', tok.line, tok.col, op='and', l=left, r=self.not_())
        return left

    def not_(self):
        if self.at('not'):
            tok = self.eat('not')
            return N('un', tok.line, tok.col, op='not', e=self.not_())
        return self.cmp()

    def cmp(self):
        left = self.add()
        if self.peek().kind in ('==', '!=', '<', '>', '<=', '>='):
            tok = self.peek()
            self.i += 1
            left = N('bin', tok.line, tok.col, op=tok.kind, l=left, r=self.add())
        return left

    def add(self):
        left = self.mul()
        while self.peek().kind in ('+', '-'):
            tok = self.peek()
            self.i += 1
            left = N('bin', tok.line, tok.col, op=tok.kind, l=left, r=self.mul())
        return left

    def mul(self):
        left = self.unary()
        while self.peek().kind in ('*', '/', '//', '%'):
            tok = self.peek()
            self.i += 1
            left = N('bin', tok.line, tok.col, op=tok.kind, l=left, r=self.unary())
        return left

    def unary(self):
        if self.at('-'):
            tok = self.eat('-')
            return N('un', tok.line, tok.col, op='-', e=self.unary())
        return self.postfix()

    def postfix(self):
        e = self.primary()
        while True:
            if self.at('(') and e.k == 'name':
                self.i += 1
                args, named = [], []
                while not self.at(')'):
                    if self.at('NAME') and self.t[self.i + 1].kind == ':':
                        nt = self.eat('NAME')
                        self.i += 1
                        named.append((nt.val, self.expr(), nt.line, nt.col))
                    else:
                        args.append(self.expr())
                    if not self.at(')'):
                        self.eat(',', ("separate values with ','", "افصل بين القيم بـ '،'"))
                self.eat(')')
                e = N('call', e.line, e.col, name=e.name, args=args, named=named)
            elif self.at('.'):
                self.i += 1
                f = self.eat('NAME', ('write a field name after the dot', 'اكتب اسم الحقل بعد النقطة'))
                e = N('field', f.line, f.col, obj=e, name=f.val)
            elif self.at('['):
                self.i += 1
                idx = self.expr()
                self.eat(']')
                e = N('index', e.line, e.col, obj=e, idx=idx)
            else:
                return e

    def primary(self):
        tok = self.peek()
        k = tok.kind
        if k == 'INT':
            self.i += 1
            return N('int', tok.line, tok.col, v=tok.val)
        if k == 'FLOAT':
            self.i += 1
            return N('float', tok.line, tok.col, v=tok.val)
        if k == 'STR':
            self.i += 1
            parts = []
            for p in tok.val:
                if p[0] == 's':
                    parts.append(p)
                else:
                    sub = Parser(tokenize(p[1].strip() or ' ', p[2], p[3]))
                    if sub.at('EOF') or sub.at('NEWLINE'):
                        raise OktoError(
                            'E005',
                            p[2],
                            p[3],
                            exp=show('EXPR'),
                            got=("'{}'", "'{}'"),
                            fix=(
                                "put a value between the braces, or write '{{' for a literal brace",
                                "ضع قيمة بين القوسين، أو اكتب '{{' لو تريد القوس نفسه",
                            ),
                        )
                    e = sub.expr()
                    sub.eat('NEWLINE')
                    parts.append(('e', e))
            return N('str', tok.line, tok.col, parts=parts)
        if k in ('true', 'false'):
            self.i += 1
            return N('bool', tok.line, tok.col, v=(k == 'true'))
        if k == 'none':
            self.i += 1
            return N('none', tok.line, tok.col)
        if k == 'NAME':
            self.i += 1
            return N('name', tok.line, tok.col, name=tok.val)
        if k == '(':
            self.i += 1
            e = self.expr()
            self.eat(')', ("add ')'", "أضف ')'"))
            return e
        if k == '[':
            self.i += 1
            items = []
            while not self.at(']'):
                items.append(self.expr())
                if not self.at(']'):
                    self.eat(',', ("separate items with ','", "افصل بين العناصر بـ '،'"))
            self.eat(']')
            return N('list', tok.line, tok.col, items=items)
        if k == '{':
            self.i += 1
            items = []
            while not self.at('}'):
                key = self.expr()
                self.eat(':', ('write each entry as key: value', 'اكتب كل عنصر هكذا: مفتاح: قيمة'))
                items.append((key, self.expr()))
                if not self.at('}'):
                    self.eat(',', ("separate entries with ','", "افصل بين العناصر بـ '،'"))
            self.eat('}')
            return N('dict', tok.line, tok.col, items=items)
        raise OktoError('E005', tok.line, tok.col, exp=show('EXPR'), got=show_tok(tok), fix=DEFAULT_FIX)
