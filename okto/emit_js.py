"""Okto -> JavaScript (runs on Node). The Go backend comes next."""

import json

from .checker import PERMS, SIMPLE, ident, is_agg, is_dict, root_of

PRELUDE = r""""use strict";
const $fs = require("fs");
class $Err extends Error {}
function $s(v) {
  if (v === null) return "none";
  if (Array.isArray(v)) return "[" + v.map($s).join(", ") + "]";
  if (v instanceof Map) return "{" + Array.from(v, ([k, x]) => $s(k) + ": " + $s(x)).join(", ") + "}";
  if (typeof v === "object") return v.$t();
  return String(v);
}
function $copy(v) {
  if (Array.isArray(v)) return v.map($copy);
  if (v instanceof Map) return new Map(Array.from(v, ([k, x]) => [k, $copy(x)]));
  if (v !== null && typeof v === "object") return v.$c();
  return v;
}
function $idx(a, i, line) {
  if (i < 0 || i >= a.length) throw new $Err("line " + line + ": index " + i + " is outside the list (size " + a.length + ")");
  return a[i];
}
function $set(a, i, v, line) {
  if (i < 0 || i >= a.length) throw new $Err("line " + line + ": index " + i + " is outside the list (size " + a.length + ")");
  a[i] = v;
}
function $get(m, k) { return m.has(k) ? m.get(k) : null; }
function $div(a, b, line) {
  if (b === 0) throw new $Err("line " + line + ": division by zero");
  return a / b;
}
function $fdiv(a, b, line) { return Math.floor($div(a, b, line)); }
function $mod(a, b, line) {
  if (b === 0) throw new $Err("line " + line + ": division by zero");
  return ((a % b) + b) % b;
}
function $len(v) { return typeof v === "string" ? Array.from(v).length : (v instanceof Map ? v.size : v.length); }
function $contains(x, v) { return x instanceof Map ? x.has(v) : x.includes(v); }
function $slice(x, a, b, line) {
  const items = typeof x === "string" ? Array.from(x) : x;
  if (a < 0 || b > items.length || a > b) throw new $Err("line " + line + ": slice " + a + ".." + b + " is outside the size " + items.length);
  const part = items.slice(a, b);
  return typeof x === "string" ? part.join("") : part.map($copy);
}
function $sort(a) { return a.slice().sort((x, y) => (x < y ? -1 : x > y ? 1 : 0)); }
const $path = require("path");
const $crypto = require("crypto");
let $allow = { read: [], write: [], env: [] };
function $real(p) {
  const abs = $path.resolve(p);
  try { return $fs.realpathSync(abs); } catch (e) {}
  try { return $path.join($fs.realpathSync($path.dirname(abs)), $path.basename(abs)); } catch (e) {}
  return abs;
}
function $inside(target, root) {
  if (root === "*") return true;
  let t = $real(target), r = $real(root);
  if (process.platform === "win32") { t = t.toLowerCase(); r = r.toLowerCase(); }
  return t === r || t.startsWith(r.endsWith($path.sep) ? r : r + $path.sep);
}
function $perm(kind, what, target, line) {
  const exact = kind === "env" || kind === "serve";
  const ok = $allow[kind].some((r) => (exact ? r === "*" || r === target : $inside(target, r)));
  if (!ok) throw new $Err("line " + line + ": " + what + " '" + target + "' is not allowed by this program's permissions");
}
class $Secret {
  #v;
  constructor(v) { this.#v = v; }
  $c() { return this; }
  $t() { return "***"; }
  toString() { return "***"; }
  toJSON() { return "***"; }
  static open(s) { return s.#v; }
}
function $secret_equals(a, b) {
  const h = (x) => $crypto.createHash("sha256").update(x instanceof $Secret ? $Secret.open(x) : x, "utf8").digest();
  return $crypto.timingSafeEqual(h(a), h(b));
}
class $Sql {
  constructor(parts) { this.parts = parts; }
  $c() { return this; }
  $t() { return $b_sql_text(this); }
}
const $p = (v) => ({ p: v === null ? null : $s(v) });
const $sqlcat = (a, b) => new $Sql(a.parts.concat(b.parts));
const $b_sql_text = (q) => q.parts.map((x) => (typeof x === "string" ? x : "?")).join("");
const $b_sql_text_numbered = (q) => { let n = 0; return q.parts.map((x) => (typeof x === "string" ? x : "$" + ++n)).join(""); };
const $b_sql_values = (q) => q.parts.filter((x) => typeof x !== "string").map((x) => x.p);
class $Html {
  constructor(s) { this.s = s; }
  $c() { return this; }
  $t() { return this.s; }
}
const $esc = (v) => $s(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
const $htmlcat = (a, b) => new $Html(a.s + b.s);
const $MAX_BODY = 1048576;
function $webHeaders(type) {
  return { "Content-Type": type, "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY" };
}
function $webFail(res, status, text) {
  res.writeHead(status, $webHeaders("text/plain; charset=utf-8"));
  res.end(text);
}
function $webError(e) {
  if (e instanceof $Err) return e.message;
  if (e instanceof RangeError) return "too many nested calls (endless recursion?)";
  return "internal: " + e;
}
function $serve(addr, handler, makeRequest, line) {
  $perm("serve", "serving on", addr, line);
  const m = /^(\[[^\]]*\]|[^:\[\]]*):(\d{1,5})$/.exec(addr);
  if (!m || Number(m[2]) > 65535) throw new $Err("line " + line + ": the address '" + addr + "' must look like 127.0.0.1:8080");
  const host = m[1].replace(/^\[|\]$/g, "") || undefined;
  const http = require("http");
  const server = http.createServer((req, res) => {
    const chunks = [];
    let size = 0;
    req.on("data", (c) => { size += c.length; if (size <= $MAX_BODY) chunks.push(c); });
    req.on("end", () => {
      if (size > $MAX_BODY) return $webFail(res, 413, "request body too large\n");
      const url = new URL(req.url, "http://localhost");
      let path = url.pathname;
      try { path = decodeURIComponent(path); } catch (e) {}
      const query = new Map();
      for (const k of Array.from(new Set(url.searchParams.keys())).sort()) {
        const all = url.searchParams.getAll(k);
        query.set(k, all[all.length - 1]);
      }
      const headers = new Map();
      for (const k of Object.keys(req.headers).sort()) {
        const v = req.headers[k];
        headers.set(k, Array.isArray(v) ? v.join(", ") : v);
      }
      let out;
      try {
        out = handler(makeRequest(req.method, path, query, headers, Buffer.concat(chunks).toString("utf8")));
      } catch (e) {
        console.error("runtime error: " + $webError(e));
        return $webFail(res, 500, "internal server error\n");
      }
      let bad = null;
      if (!Number.isInteger(out.f_status) || out.f_status < 100 || out.f_status > 599) bad = "the response status " + out.f_status + " is not between 100 and 599";
      else if (/[\r\n]/.test(out.f_type)) bad = "the response type must be one line";
      if (bad !== null) {
        console.error("runtime error: line " + line + ": " + bad);
        return $webFail(res, 500, "internal server error\n");
      }
      res.writeHead(out.f_status, $webHeaders(out.f_type));
      res.end(out.f_body);
    });
  });
  server.headersTimeout = 10000;
  server.requestTimeout = 30000;
  server.on("error", () => {
    console.error("runtime error: line " + line + ": cannot serve on '" + addr + "' (the address is in use, or not available on this machine)");
    process.exit(1);
  });
  server.listen(Number(m[2]), host, () => console.log("serving on http://" + addr));
}
const $b_trim = (s) => s.trim();
const $b_upper = (s) => s.toUpperCase();
const $b_lower = (s) => s.toLowerCase();
const $b_split = (s, sep) => (sep === "" ? Array.from(s) : s.split(sep));
const $b_join = (a, sep) => a.join(sep);
const $b_starts_with = (s, p) => s.startsWith(p);
const $b_ends_with = (s, p) => s.endsWith(p);
const $b_replace = (s, a, b) => (a === "" ? s : s.split(a).join(b));
const $b_find = (s, p) => { const i = s.indexOf(p); return i < 0 ? null : Array.from(s.slice(0, i)).length; };
const $b_to_int = (s) => (/^\s*[+-]?\d+\s*$/.test(s) ? parseInt(s, 10) : null);
const $b_to_float = (s) => (/^\s*[+-]?(\d+\.?\d*|\.\d+)\s*$/.test(s) ? parseFloat(s) : null);
const $b_read_file = (p, line) => { $perm("read", "reading the file", p, line); try { return $fs.readFileSync(p, "utf8").replace(/^\uFEFF/, ""); } catch (e) { return null; } };
const $b_write_file = (p, t, line) => { $perm("write", "writing the file", p, line); try { $fs.writeFileSync(p, t, "utf8"); return true; } catch (e) { return false; } };
const $b_append_file = (p, t, line) => { $perm("write", "writing the file", p, line); try { $fs.appendFileSync(p, t, "utf8"); return true; } catch (e) { return false; } };
const $b_env = (n, line) => { $perm("env", "reading the environment value", n, line); const v = process.env[n]; return v === undefined ? null : v; };
const $b_secret_env = (n, line) => { const v = $b_env(n, line); return v === null ? null : new $Secret(v); };
const $b_secret_file = (p, line) => { const v = $b_read_file(p, line); return v === null ? null : new $Secret(v.replace(/[\r\n]+$/, "")); };
const $b_reveal = (s) => $Secret.open(s);
const $b_args = () => process.argv.slice(2);
try {
"""

EPILOG = r"""} catch (e) {
  if (e instanceof $Err) { console.error("runtime error: " + e.message); process.exit(1); }
  if (e instanceof RangeError) { console.error("runtime error: too many nested calls (endless recursion?)"); process.exit(1); }
  throw e;
}
"""

OPS = {'and': '&&', 'or': '||', '==': '===', '!=': '!==', '??': '??'}
FRESH = ('call', 'list', 'dict')  # these always produce a new value: no copy needed


class Emitter:
    def __init__(self):
        self.lines, self.ind, self.n = [], 1, 0
        self.file = ''  # the used file being written ('' for the main file)

    def w(self, s):
        self.lines.append('  ' * self.ind + s)

    def ln(self, line):
        """A line number as generated code. In a used file it names the file too:
        the run time prints 'line ' + this, so the message reads 'line 5 of lib/tools.ok'."""
        if not self.file:
            return str(line)
        return json.dumps('%d of %s' % (line, self.file), ensure_ascii=False)

    def program(self, ast):
        allow = {'read': [], 'write': [], 'env': [], 'serve': []}
        for s in ast:
            if s.k == 'allow':
                allow[s.kind].append(s.value)
        self.w('$allow = %s;' % json.dumps(allow, ensure_ascii=False))
        for s in ast:
            if s.k == 'record':
                self.record(s)
        for s in ast:
            if s.k not in ('record', 'allow', 'use'):
                mod = getattr(s, 'mod', None)
                self.file = mod.rel if mod is not None and mod.name else ''
                self.stmt(s)
        return PRELUDE + '\n'.join(self.lines) + '\n' + EPILOG

    def record(self, s):
        fields = ['f_' + f[0] for f in s.fields]
        cls = 'R_' + ident(s.name)
        self.w('class %s {' % cls)
        self.ind += 1
        self.w('constructor(%s) { %s }' % (', '.join(fields), ' '.join('this.%s = %s;' % (f, f) for f in fields)))
        self.w('$c() { return new %s(%s); }' % (cls, ', '.join('$copy(this.%s)' % f for f in fields)))
        shown = ' + ", " + '.join('"%s: " + $s(this.%s)' % (f[0], 'f_' + f[0]) for f in s.fields)
        self.w(
            '$t() { return %s + "(" + %s + ")"; }'
            % (json.dumps(getattr(s, 'shown', s.name), ensure_ascii=False), shown or '""')
        )
        self.ind -= 1
        self.w('}')

    def body(self, block):
        self.ind += 1
        for s in block:
            self.stmt(s)
        self.ind -= 1

    @staticmethod
    def name(n):
        return 'u_' + ident(n)

    # ---- statements -------------------------------------------------
    def stmt(self, s):
        k = s.k
        if k == 'decl':
            self.w(
                '%s %s = %s;'
                % ('let' if s.mutable else 'const', self.name(getattr(s, 'full', s.name)), self.val(s.value))
            )
        elif k == 'assign':
            tg = s.target
            if tg.k == 'name':
                self.w('%s = %s;' % (self.name(getattr(tg, 'full', tg.name)), self.val(s.value)))
            elif tg.k == 'field':
                self.w('%s.f_%s = %s;' % (self.ex(tg.obj), tg.name, self.val(s.value)))
            elif is_dict(tg.obj.t):
                self.w('%s.set(%s, %s);' % (self.ex(tg.obj), self.ex(tg.idx), self.val(s.value)))
            else:
                self.w('$set(%s, %s, %s, %s);' % (self.ex(tg.obj), self.ex(tg.idx), self.val(s.value), self.ln(s.line)))
        elif k == 'expr':
            self.w(self.ex(s.e) + ';')
        elif k == 'if':
            self.w('if (%s) {' % self.ex(s.cond))
            self.body(s.then)
            if s.other is not None:
                self.w('} else {')
                self.body(s.other)
            self.w('}')
        elif k == 'while':
            self.w('while (%s) {' % self.ex(s.cond))
            self.body(s.body)
            self.w('}')
        elif k == 'for':
            if s.is_range:
                self.n += 1
                a = s.it.args
                lo = '0' if len(a) == 1 else self.ex(a[0])
                hi = self.ex(a[-1])
                i, n = '$i%d' % self.n, '$n%d' % self.n
                self.w('for (let %s = %s, %s = %s; %s < %s; %s++) {' % (i, lo, n, hi, i, n, i))
                self.ind += 1
                self.w('const %s = %s;' % (self.name(s.name), i))
                self.ind -= 1
            else:
                src = self.ex(s.it)
                root = root_of(s.it)
                if s.it.k not in FRESH and (root is None or root.var.mutable):
                    # the body may change the list: loop over a snapshot
                    src = '$copy(%s)' % src if is_agg(s.it.t[1]) else src + '.slice()'
                self.w('for (const %s of %s) {' % (self.name(s.name), src))
            self.body(s.body)
            self.w('}')
        elif k == 'fn':
            self.w('function %s(%s) {' % (self.name(s.name), ', '.join(self.name(p[0]) for p in s.params)))
            self.body(s.body)
            self.w('}')
        elif k == 'return':
            self.w('return;' if s.value is None else 'return %s;' % self.val(s.value))
        elif k in ('break', 'continue'):
            self.w(k + ';')
        else:
            raise AssertionError(k)

    # ---- expressions ------------------------------------------------
    def val(self, e):
        """A value that will be stored: lists, dicts and records are copied,
        so two names never share one value."""
        js = self.ex(e)
        if e.k not in FRESH and is_agg(e.t):
            return '$copy(%s)' % js
        return js

    def arg(self, e):
        """A value passed to a function. Parameters cannot be changed, so a copy is
        needed only when the function could change the original: a global var."""
        js = self.ex(e)
        if e.k not in FRESH and is_agg(e.t):
            root = root_of(e)
            if root is None or (root.var.mutable and root.var.kind == 'global'):
                return '$copy(%s)' % js
        return js

    def ex(self, e):
        k = e.k
        if k == 'int':
            return str(e.v)
        if k == 'float':
            return repr(e.v)
        if k == 'bool':
            return 'true' if e.v else 'false'
        if k == 'none':
            return 'null'
        if k == 'str':
            if len(e.parts) == 1 and e.parts[0][0] == 's':
                return json.dumps(e.parts[0][1], ensure_ascii=False)
            bits = [json.dumps(p[1], ensure_ascii=False) if p[0] == 's' else '$s(%s)' % self.ex(p[1]) for p in e.parts]
            return '(' + ' + '.join(['""', *bits]) + ')'
        if k == 'name':
            return self.name(getattr(e, 'full', e.name))
        if k == 'un':
            return '(%s%s)' % ('!' if e.op == 'not' else '-', self.ex(e.e))
        if k == 'bin':
            lhs, r = self.ex(e.l), self.ex(e.r)
            if e.op == '/':
                return '$div(%s, %s, %s)' % (lhs, r, self.ln(e.line))
            if e.op == '//':
                return '$fdiv(%s, %s, %s)' % (lhs, r, self.ln(e.line))
            if e.op == '%':
                return '$mod(%s, %s, %s)' % (lhs, r, self.ln(e.line))
            if e.op == '+' and e.t == 'sql':
                return '$sqlcat(%s, %s)' % (lhs, r)
            if e.op == '+' and e.t == 'html':
                return '$htmlcat(%s, %s)' % (lhs, r)
            return '(%s %s %s)' % (lhs, OPS.get(e.op, e.op), r)
        if k == 'field':
            return '%s.f_%s' % (self.ex(e.obj), e.name)
        if k == 'index':
            if is_dict(e.obj.t):
                return '$get(%s, %s)' % (self.ex(e.obj), self.ex(e.idx))
            return '$idx(%s, %s, %s)' % (self.ex(e.obj), self.ex(e.idx), self.ln(e.line))
        if k == 'list':
            return '[' + ', '.join(self.val(i) for i in e.items) + ']'
        if k == 'dict':
            return 'new Map([' + ', '.join('[%s, %s]' % (self.ex(a), self.val(b)) for a, b in e.items) + '])'
        if k == 'call':
            return self.call(e)
        raise AssertionError(k)

    def call(self, e):
        if e.rec is not None:
            given = {n[0]: n[1] for n in e.named}
            return 'new R_%s(%s)' % (ident(e.rec.name), ', '.join(self.val(given[f[0]]) for f in e.rec.fields))
        b = e.builtin
        if b is None:
            return '%s(%s)' % (self.name(getattr(e, 'full', e.name)), ', '.join(self.arg(a) for a in e.args))
        if b == 'sql':
            parts = [
                json.dumps(p[1], ensure_ascii=False) if p[0] == 's' else '$p(%s)' % self.ex(p[1])
                for p in e.args[0].parts
            ]
            return 'new $Sql([%s])' % ', '.join(parts)
        if b == 'html':
            bits = [
                json.dumps(p[1], ensure_ascii=False)
                if p[0] == 's'
                else ('%s.s' % self.ex(p[1]) if p[1].t == 'html' else '$esc(%s)' % self.ex(p[1]))
                for p in e.args[0].parts
            ]
            return 'new $Html(%s)' % ' + '.join(['""', *bits])
        if b == 'serve':
            return '$serve(%s, %s, (m, p, q, h, b) => new R_Request(m, p, q, h, b), %s)' % (
                self.ex(e.args[0]),
                self.name(e.handler.name),
                self.ln(e.line),
            )
        a = [self.ex(x) for x in e.args]
        if b in SIMPLE:
            if b in PERMS:
                a.append(self.ln(e.line))
            return '$b_%s(%s)' % (b, ', '.join(a))
        if b == 'secret_equals':
            return '$secret_equals(%s, %s)' % (a[0], a[1])
        if b == 'print':
            return 'console.log([%s].map($s).join(" "))' % ', '.join(a)
        if b == 'len':
            return '$len(%s)' % a[0]
        if b == 'to_text':
            return '$s(%s)' % a[0]
        if b == 'contains':
            return '$contains(%s, %s)' % (a[0], a[1])
        if b == 'slice':
            return '$slice(%s, %s, %s, %s)' % (a[0], a[1], a[2], self.ln(e.line))
        if b == 'keys':
            return 'Array.from(%s.keys())' % a[0]
        if b == 'sort':
            return '$sort(%s)' % a[0]
        if b == 'push':
            return '%s.push(%s)' % (a[0], self.val(e.args[1]))
        if b == 'remove':
            return '%s.delete(%s)' % (a[0], a[1])
        raise AssertionError(b)
