/* The playground worker (a module worker): loads Python (Pyodide), the Okto compiler from this site,
   compiles the program to JavaScript and runs it here, away from the page.
   The page stops this worker if a program runs too long. */

const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";
const MAX_LINES = 5000;
let compile = null;

async function boot() {
  const { loadPyodide } = await import(PYODIDE + "pyodide.mjs");
  const manifest = await (await fetch("manifest.json")).json();
  const py = await loadPyodide({ indexURL: PYODIDE });
  py.FS.mkdirTree("/okto_site/okto");
  for (const name of manifest.modules) {
    const text = await (await fetch("okto/" + name)).text();
    py.FS.writeFile("/okto_site/okto/" + name, text);
  }
  compile = py.runPython(`
import json, sys
sys.path.insert(0, "/okto_site")
from okto.cli import compile_source

def okto_compile(src, lang):
    code, errors = compile_source(src, "js")
    lines = src.splitlines()
    return json.dumps({
        "code": code,
        "errors": [e.as_dict(lang) for e in errors],
        "text": "\\n\\n".join(e.render("main.ok", lines, lang) for e in errors),
    })

okto_compile
`);
}

/* The browser has no files and no environment values. These small stand-ins
   let the Okto run time work; file access simply fails, as a missing file would. */
function normalize(p) {
  const parts = [];
  for (const part of p.split("/")) {
    if (part === "" || part === ".") continue;
    if (part === "..") parts.pop();
    else parts.push(part);
  }
  return "/" + parts.join("/");
}
const noFiles = () => { throw new Error("there are no files in the browser"); };
const pathStub = {
  sep: "/",
  resolve: (p) => normalize(p.startsWith("/") ? p : "/playground/" + p),
  join: (a, b) => normalize(a + "/" + b),
  dirname: (p) => normalize(p + "/.."),
  basename: (p) => p.split("/").pop(),
};
const fsStub = { realpathSync: noFiles, readFileSync: noFiles, writeFileSync: noFiles, appendFileSync: noFiles };
const cryptoStub = { createHash: () => { throw new Error("secrets are not available in the browser"); } };

function execute(code) {
  const out = [];
  const EXIT = { exit: true };
  const LIMIT = { limit: true };
  let status = 0;
  const add = (kind, values) => {
    if (out.length >= MAX_LINES) throw LIMIT;
    out.push({ kind, text: values.map(String).join(" ") });
  };
  const fakeConsole = { log: (...v) => add("out", v), error: (...v) => add("err", v) };
  const fakeProcess = { platform: "linux", env: {}, argv: ["okto", "main.ok"], exit: (c) => { status = c; throw EXIT; } };
  const fakeRequire = (name) => ({ fs: fsStub, path: pathStub, crypto: cryptoStub })[name];
  try {
    new Function("require", "process", "console", code)(fakeRequire, fakeProcess, fakeConsole);
  } catch (e) {
    if (e === LIMIT) {
      out.push({ kind: "note", text: "(stopped: more than " + MAX_LINES + " lines of output)" });
      status = 1;
    } else if (e !== EXIT) {
      out.push({ kind: "err", text: "internal error: " + e });
      status = 1;
    }
  }
  return { out, status };
}

const ready = boot();
ready.catch(() => {}); // the error is reported to the page with the first request

self.onmessage = async (event) => {
  // Only the page that started this worker may use it, and only with the expected message shape.
  if (event.origin !== "" && event.origin !== self.location.origin) return;
  const data = event.data;
  if (typeof data !== "object" || data === null || typeof data.source !== "string") return;
  const id = Number(data.id);
  const source = data.source;
  const lang = data.lang === "ar" ? "ar" : "en";
  const mode = data.mode === "check" ? "check" : "run";
  try {
    await ready;
  } catch (e) {
    self.postMessage({ id, kind: "failed", text: "The compiler could not load (" + e + "). Check the connection and reload the page." });
    return;
  }
  try {
    self.postMessage({ id, kind: "ready" });
    const result = JSON.parse(compile(source, lang));
    if (result.errors.length || mode === "check") {
      self.postMessage({ id, kind: "checked", errors: result.errors, text: result.text });
      return;
    }
    const started = performance.now();
    const { out, status } = execute(result.code);
    self.postMessage({ id, kind: "ran", out, status, ms: Math.round(performance.now() - started) });
  } catch (e) {
    self.postMessage({ id, kind: "failed", text: String(e) });
  }
};
