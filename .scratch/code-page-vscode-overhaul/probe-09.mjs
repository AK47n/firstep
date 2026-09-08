// 09 探针：5000 行文件逐键输入的真实耗时（sync 全链路）。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-page-vscode-overhaul", "sample-proj");
const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
};
let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
const page = targets.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + JSON.stringify(r.result.exceptionDetails));
  return r.result?.result?.value;
};
await Eval(`window.__smokeMarker = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100; i++) {
  if (await Eval(`document.readyState === 'complete' && !window.__smokeMarker && !!document.getElementById('code-viewer')`)) break;
  await new Promise((r) => setTimeout(r, 300));
}
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
for (let i = 0; i < 40; i++) {
  if (await Eval(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`)) break;
  await new Promise((r) => setTimeout(r, 300));
}
await Eval(`document.querySelector('#code-tree [data-code-file="big.c"]')?.click()`);
for (let i = 0; i < 60; i++) {
  if (await Eval(`(document.querySelector('#code-viewer .code-ta')?.value.length || 0) > 100000`)) break;
  await new Promise((r) => setTimeout(r, 500));
}
// 逐键输入耗时（光标在文件尾 === 最坏情形：窗口在底部，text 全量同步）
const res = await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
  const times = [];
  for (let k = 0; k < 10; k++) {
    ta.value += 'x';
    const t0 = performance.now();
    ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
    times.push(performance.now() - t0);
  }
  return times.map((t) => t.toFixed(1));
})()`);
console.log("input sync 10 次耗时(ms):", JSON.stringify(res));
console.log("has highlight spans:", await Eval(`document.querySelectorAll('#code-viewer .code-hl span').length > 0`));
process.exit(0);
