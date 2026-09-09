// 诊断（code-editor-vscode-polish/07 冒烟最后一项失败排查）：占位整块替换 → 全部展开。
// 复刻 smoke-07 尾部两步并逐态 dump。只读探测 + 只写本目录 sample-proj 夹具。
import { mkdirSync, writeFileSync, appendFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const LOG = join(ROOT, ".scratch", "code-editor-vscode-polish", "probe-ph.log");
writeFileSync(LOG, "");
const log = (s) => { appendFileSync(LOG, s + "\n"); console.log(s); };
setTimeout(() => { log("WATCHDOG"); process.exit(3); }, 60000).unref?.();

const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
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

const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + JSON.stringify(r.result.exceptionDetails));
  return r.result?.result?.value;
};
const waitFor = async (expr, ms = 8000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};

await Eval(`window.__phMarker = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__phMarker
      && !!document.getElementById('tab-code') && !!document.getElementById('code-viewer')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
log("page ready=" + ready);

await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
await Eval(`document.querySelector('button[data-tab="code"]')?.click(); true`);
await new Promise((r) => setTimeout(r, 400));

const dump = (tag) => Eval(`(async () => {
  const m = await import('/js/ui/codeeditor.js');
  const box = document.getElementById('code-viewer');
  const ta = box.querySelector('.code-ta');
  const tab = m.getActiveTab();
  return {
    tag: ${JSON.stringify(tag)},
    value: ta.value,
    sel: [ta.selectionStart, ta.selectionEnd],
    gutterLines: box.querySelectorAll('.code-gutter-line').length,
    gutterText: [...box.querySelectorAll('.code-gutter-line')].map((e) => e.textContent).join('|'),
    ph: box.querySelectorAll('.code-gutter-ph').length,
    model: tab ? tab.content : null,
  };
})()`).then((r) => { log(JSON.stringify(r)); return r; });

// 1) 折叠（光标落 helper 处）
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  const at = ta.value.indexOf('helper');
  ta.setSelectionRange(at, at);
  document.dispatchEvent(new KeyboardEvent('keydown', {
    key: '[', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true }));
  return true;
})()`);
log("folded=" + await waitFor(`!!document.querySelector('#code-viewer .code-gutter-ph')`));
await dump("after fold");

// 2) 折叠态编辑（复刻 smoke-07：把 'void helper' 换成 'void helper2'）
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  const at = ta.value.indexOf('helper');
  ta.value = ta.value.slice(0, at) + 'void helper2' + ta.value.slice(at + 'void helper'.length);
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 400));
await dump("after edit helper2");

// 3) 占位整块替换（失败项）
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value.replace('… 2 行', 'NEW');
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 600));
await dump("after replace placeholder");

// 4) 再派发一次 input（无内容变化）——看占位 gutter 行是否只是渲染残留
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 600));
await dump("after no-op input");

log("DONE");
process.exit(0);
