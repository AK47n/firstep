// 调试 fold 首次折叠状态（干净重跑）
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const SAMPLE = join(ROOT, ".scratch", "code-editor-vscode-polish", "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), [
  "void helper(void) {",
  "    int x = 0;",
  "}",
  "",
  "int main(void) {",
  "    helper();",
  "    return 0;",
  "}",
].join("\n"));

const targets = await (await fetch("http://127.0.0.1:9251/json/list")).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
const waitFor = async (expr, ms = 8000) => {
  for (let i = 0; i < ms / 200; i++) { try { if (await Eval(expr)) return true; } catch {} await new Promise((r) => setTimeout(r, 200)); }
  return false;
};

await Eval(`window.__smokeMarker = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
await waitFor(`document.readyState === 'complete' && !window.__smokeMarker && !!document.getElementById('code-viewer')`);
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
console.log("before:", await Eval(`JSON.stringify([...document.querySelectorAll('#code-viewer .code-gutter-line')].map((x) => x.dataset.codeLine))`));
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(ta.value.indexOf('helper'), ta.value.indexOf('helper'));
  document.dispatchEvent(new KeyboardEvent('keydown', { key: '[', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true }));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 400));
console.log("after:", await Eval(`(() => {
  const g = [...document.querySelectorAll('#code-viewer .code-gutter-line')].map((x) => x.dataset.codeLine);
  const ta = document.querySelector('#code-viewer .code-ta');
  return JSON.stringify({ gutter: g, ph: !!document.querySelector('#code-viewer .code-gutter-ph'), val: ta.value, sel: ta.selectionStart });
})()`));
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.editJumpToLine(2))`);
await new Promise((r) => setTimeout(r, 400));
console.log("afterJump:", await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  return JSON.stringify({
    ph: !!document.querySelector('#code-viewer .code-gutter-ph'),
    sel: ta.selectionStart,
    idxIntX: ta.value.indexOf('int x'),
  });
})()`));
process.exit(0);
