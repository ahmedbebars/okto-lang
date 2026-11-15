/* The playground page: sends the program to the worker and shows the result. */
"use strict";

const TIME_LIMIT_MS = 5000; // the longest a program may run
const LOAD_LIMIT_MS = 120000; // the longest loading the compiler may take on a slow line
const $ = (id) => document.getElementById(id);
const editor = $("editor");
const output = $("output");
const status = $("status");
const picker = $("example");
const arabic = $("arabic");
let worker = null;
let request = 0;
let timer = null;
let examples = {};

function startWorker() {
  worker = new Worker("worker.js", { type: "module" });
  worker.onmessage = onResult;
  worker.onerror = () => show([{ kind: "err", text: "The compiler could not start. Check your connection and reload." }], "error");
}

function show(lines, state, note) {
  output.replaceChildren(
    ...lines.map((line) => {
      const div = document.createElement("div");
      div.className = "line " + line.kind;
      div.dir = "auto";
      div.textContent = line.text === "" ? " " : line.text;
      return div;
    })
  );
  status.dataset.state = state;
  status.textContent = note || "";
}

function send(mode) {
  clearTimeout(timer);
  request += 1;
  const id = request;
  show([], "busy", "Working… (the first run loads the compiler, about 10 MB, then it is cached)");
  worker.postMessage({ id, mode, source: editor.value, lang: arabic.checked ? "ar" : "en" });
  timer = setTimeout(() => {
    if (id !== request) return;
    worker.terminate();
    startWorker();
    show([{ kind: "err", text: "Stopped: the program ran for more than " + TIME_LIMIT_MS / 1000 + " seconds." }], "error");
  }, LOAD_LIMIT_MS);
}

function onResult(event) {
  const msg = event.data;
  if (msg.id !== request) return;
  if (msg.kind === "ready") {
    // The compiler is loaded: from now on only the program's own time counts.
    clearTimeout(timer);
    timer = setTimeout(() => {
      worker.terminate();
      startWorker();
      show([{ kind: "err", text: "Stopped: the program ran for more than " + TIME_LIMIT_MS / 1000 + " seconds." }], "error");
    }, TIME_LIMIT_MS);
    return;
  }
  clearTimeout(timer);
  if (msg.kind === "checked") {
    if (msg.errors.length === 0) {
      show([{ kind: "ok", text: arabic.checked ? "تمام: لا توجد أخطاء" : "ok: no errors" }], "ok", "Checked");
    } else {
      const lines = msg.text.split("\n").map((text) => ({ kind: "err", text }));
      show(lines, "error", msg.errors.length + " error(s). Nothing was run.");
    }
  } else if (msg.kind === "ran") {
    show(msg.out, msg.status === 0 ? "ok" : "error", "Finished in " + msg.ms + " ms" + (msg.status ? " (exit code " + msg.status + ")" : ""));
  } else {
    show([{ kind: "err", text: msg.text }], "error");
  }
}

function encode(text) {
  const bytes = new TextEncoder().encode(text);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function decode(code) {
  const bin = atob(code.replace(/-/g, "+").replace(/_/g, "/"));
  return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
}

async function init() {
  startWorker();
  const manifest = await (await fetch("manifest.json", { cache: "no-cache" })).json();
  examples = manifest.examples;
  for (const el of document.querySelectorAll("[data-version]")) el.textContent = manifest.version;
  for (const name of Object.keys(examples)) picker.add(new Option(name, name));
  const shared = new URLSearchParams(location.hash.slice(1)).get("code");
  if (shared) {
    try {
      editor.value = decode(shared);
      picker.value = "";
    } catch (e) {
      editor.value = examples["hello.ok"];
    }
  } else {
    editor.value = examples["hello.ok"];
  }
}

picker.addEventListener("change", () => {
  if (examples[picker.value]) editor.value = examples[picker.value];
  output.replaceChildren();
  status.textContent = "";
});

editor.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    send("run");
  } else if (e.key === "Tab" && !e.shiftKey) {
    // Okto does not accept tab characters: indent with 4 spaces.
    e.preventDefault();
    editor.setRangeText("    ", editor.selectionStart, editor.selectionEnd, "end");
  }
});

$("run").addEventListener("click", () => send("run"));
$("check").addEventListener("click", () => send("check"));
$("share").addEventListener("click", async () => {
  const url = location.origin + location.pathname + "#code=" + encode(editor.value);
  history.replaceState(null, "", url);
  try {
    await navigator.clipboard.writeText(url);
    status.textContent = "Link copied";
  } catch (e) {
    status.textContent = "Link is in the address bar";
  }
});

init();
