// 诊断 3（overhaul/01 折叠 + 保存回归面）：真实交互路径逐条探测。同步日志 + 看门狗。
import { mkdirSync, writeFileSync, appendFileSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const LOG = join(ROOT, ".scratch", "code-page-vscode-overhaul", "probe-fold.log");
writeFileSync(LOG, "");
const log = (s) => { appendFileSync(LOG, s + "\n"); console.log(s); };
setTimeout(() => { log("WATCHDOG —— 上一步是卡死点"); process.exit(3); }, 90000).unref?.();

const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-page-vscode-overhaul");
const SAMPLE = join(OUT, "sample-proj");
const MAIN_C = join(SAMPLE, "main.c");
mkdirSync(SAMPLE, { recursive: true });
const ORIGINAL = ["void helper(void) {", "    int x = 0;", "}"].join("\n");
writeFileSync(MAIN_C, ORIGINAL);

const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
log("ws open");
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

await Eval(`window.__foldMarker = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__foldMarker
      && !!document.getElementById('tab-code') && !!document.getElementById('code-viewer')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
log("page ready=" + ready);

await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
// 激活「代码」tab（Ctrl+S / 折叠快捷键都要求 #tab-code 激活）
await Eval(`document.querySelector('button[data-tab="code"]')?.click(); true`);
await new Promise((r) => setTimeout(r, 400));
log("code tab active=" + await Eval(`document.getElementById('tab-code')?.classList.contains('active')`));

const state = () => Eval(`(() => {
  const box = document.getElementById('code-viewer');
  const ta = box.querySelector('.code-ta');
  return {
    value: ta.value,
    lines: box.querySelectorAll('.code-hl-line').length,
    arrows: box.querySelectorAll('[data-fold]').length,
    placeholders: box.querySelectorAll('[data-fold-expand]').length,
    gutterText: [...box.querySelectorAll('.code-gutter-line')].map((e) => e.textContent).join('|'),
  };
})()`);

log("A 未折叠初始态: " + JSON.stringify(await state()));

// 键盘折叠：光标落进函数体（模型偏移 20 = 第 2 行内）
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus(); ta.setSelectionRange(20, 20); return true;
})()`);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: '[', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true })); true`);
const folded = await waitFor(`document.querySelectorAll('#code-viewer [data-fold-expand]').length > 0`, 3000);
log("B Ctrl+Shift+[ 折叠=" + folded + " " + JSON.stringify(await state()));

// 点击 gutter 箭头（折叠态 ▸）展开
await Eval(`document.querySelector('#code-viewer [data-fold]')?.click(); true`);
const expandedByArrow = await waitFor(`document.querySelectorAll('#code-viewer [data-fold-expand]').length === 0`, 3000);
log("C 点箭头展开=" + expandedByArrow + " " + JSON.stringify(await state()));

// 再折叠 → 点占位行展开
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus(); ta.setSelectionRange(20, 20); return true;
})()`);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: '[', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true })); true`);
await waitFor(`document.querySelectorAll('#code-viewer [data-fold-expand]').length > 0`, 3000);
await Eval(`document.querySelector('#code-viewer [data-fold-expand]')?.click(); true`);
const expandedByPh = await waitFor(`document.querySelectorAll('#code-viewer [data-fold-expand]').length === 0`, 3000);
log("D 点占位行展开=" + expandedByPh + " " + JSON.stringify(await state()));

// Ctrl+Shift+] 展开（先折叠）
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus(); ta.setSelectionRange(20, 20); return true;
})()`);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: '[', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true })); true`);
await waitFor(`document.querySelectorAll('#code-viewer [data-fold-expand]').length > 0`, 3000);
await Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.setSelectionRange(0, 0); return true; })()`);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: ']', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true })); true`);
const expandedByKey = await waitFor(`document.querySelectorAll('#code-viewer [data-fold-expand]').length === 0`, 3000);
log("E Ctrl+Shift+] 展开=" + expandedByKey + " " + JSON.stringify(await state()));

// 保存：编辑 → 脏点 → Ctrl+S → 脏点清 + 磁盘更新
const SAVE_TEXT = "int main(void) {\n    return 0;\n}\n";
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus(); ta.value = ${JSON.stringify(SAVE_TEXT)}; ta.setSelectionRange(0, 0);
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 500));
log("F 编辑后 脏点=" + await Eval(`document.querySelectorAll('.code-tab-dirty').length`)
  + " value=" + JSON.stringify((await state()).value));
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true, cancelable: true })); true`);
const saved = await waitFor(`document.querySelectorAll('.code-tab-dirty').length === 0`, 8000);
log("G Ctrl+S 保存=" + saved
  + " toast=" + JSON.stringify(await Eval(`(document.querySelector('.toast')?.textContent || '').trim()`))
  + " disk=" + JSON.stringify(readFileSync(MAIN_C, "utf8")));

log("DONE");
process.exit(0);
