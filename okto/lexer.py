"""Okto lexer: text -> tokens. Keywords exist in English and in Arabic."""

import unicodedata

from .errors import OktoError

KEYWORDS = {
    'let',
    'var',
    'fn',
    'return',
    'if',
    'elif',
    'else',
    'while',
    'for',
    'in',
    'and',
    'or',
    'not',
    'true',
    'false',
    'none',
    'break',
    'continue',
    'record',
    'allow',
}

# Arabic keywords, written without hamza (norm() removes it before lookup).
AR_KEYWORDS = {
    'ثابت': 'let',
    'متغير': 'var',
    'دالة': 'fn',
    'ارجع': 'return',
    'اذا': 'if',
    'لو': 'if',
    'والا': 'else',
    'طالما': 'while',
    'لكل': 'for',
    'في': 'in',
    'و': 'and',
    'او': 'or',
    'ليس': 'not',
    'صح': 'true',
    'خطا': 'false',
    'فارغ': 'none',
    'توقف': 'break',
    'استمر': 'continue',
    'سجل': 'record',
    'اسمح': 'allow',
}

OPS2 = ('==', '!=', '<=', '>=', '->', '//', '??')
OPS1 = '+-*/%<>=()[]{},:?.'
ESCAPES = {'n': '\n', 't': '\t', '"': '"', '\\': '\\', '{': '{', '}': '}'}


def norm(s):
    """Forgiving Arabic spelling: drop hamza forms, tatweel and diacritics."""
    out = []
    for ch in s:
        if ch in 'أإآ':
            ch = 'ا'
        elif ch == 'ـ' or unicodedata.category(ch) == 'Mn':
            continue
        out.append(ch)
    return ''.join(out)


class Tok:
    __slots__ = ('col', 'kind', 'line', 'val')

    def __init__(self, kind, val, line, col):
        self.kind, self.val, self.line, self.col = kind, val, line, col


def _read_string(line, i, ln, col0):
    """Read a text starting at line[i] == '"'. Returns (parts, next index).
    parts is a list of ('s', text) and ('e', source, line, col) for {expr}."""
    start = i
    parts, buf = [], ''
    i += 1
    n = len(line)
    while True:
        if i >= n:
            raise OktoError('E004', ln, col0 + start + 1)
        c = line[i]
        if c == '"':
            break
        if c == '\\' and i + 1 < n and line[i + 1] in ESCAPES:
            buf += ESCAPES[line[i + 1]]
            i += 2
            continue
        if c == '{':
            if line[i + 1 : i + 2] == '{':
                buf += '{'
                i += 2
                continue
            j = line.find('}', i + 1)
            if j < 0:
                raise OktoError('E006', ln, col0 + i + 1)
            if buf:
                parts.append(('s', buf))
                buf = ''
            parts.append(('e', line[i + 1 : j], ln, col0 + i + 1))
            i = j + 1
            continue
        if c == '}' and line[i + 1 : i + 2] == '}':
            buf += '}'
            i += 2
            continue
        buf += c
        i += 1
    if buf or not parts:
        parts.append(('s', buf))
    return parts, i + 1


def tokenize(src, line0=1, col0=0):
    toks, stack, depth = [], [0], 0
    lines = src.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    ln = line0
    for k, raw in enumerate(lines):
        ln = line0 + k
        line = raw.rstrip()
        body = line.lstrip(' \t')
        if depth == 0:
            if not body or body[0] == '#':
                continue
            lead = line[: len(line) - len(body)]
            if '\t' in lead:
                raise OktoError('E002', ln, 1)
            ind = len(lead)
            if ind > stack[-1]:
                stack.append(ind)
                toks.append(Tok('INDENT', '', ln, 1))
            else:
                while ind < stack[-1]:
                    stack.pop()
                    toks.append(Tok('DEDENT', '', ln, 1))
                if ind != stack[-1]:
                    raise OktoError('E003', ln, 1)
        i = len(line) - len(body)
        n = len(line)
        while i < n:
            c = line[i]
            col = col0 + i + 1
            if c in ' \t':
                i += 1
                continue
            if c == '#':
                break
            if c.isdecimal():
                j = i
                while j < n and line[j].isdecimal():
                    j += 1
                if j + 1 < n and line[j] == '.' and line[j + 1].isdecimal():
                    j += 1
                    while j < n and line[j].isdecimal():
                        j += 1
                    toks.append(Tok('FLOAT', float(line[i:j]), ln, col))
                else:
                    toks.append(Tok('INT', int(line[i:j]), ln, col))
                i = j
                continue
            if c == '_' or c.isalpha():
                j = i + 1
                while j < n and (line[j] == '_' or line[j].isalnum() or unicodedata.category(line[j]) == 'Mn'):
                    j += 1
                word = line[i:j]
                kind = word if word in KEYWORDS else AR_KEYWORDS.get(norm(word), 'NAME')
                toks.append(Tok(kind, word, ln, col))
                i = j
                continue
            if c == '"':
                parts, j = _read_string(line, i, ln, col0)
                toks.append(Tok('STR', parts, ln, col))
                i = j
                continue
            two = line[i : i + 2]
            if two in OPS2:
                toks.append(Tok(two, two, ln, col))
                i += 2
                continue
            if c == '،':
                c = ','
            if c in OPS1:
                if c in '([{':
                    depth += 1
                elif c in ')]}':
                    depth = max(0, depth - 1)
                toks.append(Tok(c, c, ln, col))
                i += 1
                continue
            raise OktoError('E001', ln, col, ch=c)
        if depth == 0:
            toks.append(Tok('NEWLINE', '', ln, col0 + n + 1))
    if depth > 0:
        toks.append(Tok('NEWLINE', '', ln, 1))
    while len(stack) > 1:
        stack.pop()
        toks.append(Tok('DEDENT', '', ln, 1))
    toks.append(Tok('EOF', '', ln, 1))
    return toks
