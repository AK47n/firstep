// 09 探针 3：微基准——大 textarea 上各同步操作的真实耗时。
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
const out = await Eval(`(() => {
  const box = document.getElementById('code-viewer');
  const ta = document.querySelector('#code-viewer .code-ta');
  const edit = document.querySelector('#code-viewer .code-edit');
  const probe = document.querySelector('#code-viewer .code-window-probe');
  const t1 = performance.now();
  ta.value = ta.value; box.scrollTop = box.scrollTop; box.scrollLeft = box.scrollLeft;
  const t2 = performance.now();
  ta.setSelectionRange(5, 5);
  const t3 = performance.now();
  ta.focus();
  const t4 = performance.now();
  probe.textContent = 'x'; probe.getBoundingClientRect();
  const t5 = performance.now();
  probe.textContent = 'a'.repeat(40); probe.getBoundingClientRect();
  const t6 = performance.now();
  edit.style.height = edit.style.height; edit.getBoundingClientRect();
  const t7 = performance.now();
  return {
    scrollReset: (t2 - t1).toFixed(1),
    setSel: (t3 - t2).toFixed(1),
    focus: (t4 - t3).toFixed(1),
    probeSmall: (t5 - t4).toFixed(1),
    probe40: (t6 - t5).toFixed(1),
    editLayout: (t7 - t6).toFixed(1),
  };
})()`);
console.table([out]);
process.exit(0);
