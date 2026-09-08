// 调试探针：打开 big.c 后检查树/编辑器状态。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
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
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
const cdp = (method, params = {}) => new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + JSON.stringify(r.result.exceptionDetails));
  return r.result?.result?.value;
};
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer("${ROOT.replace(/\\/g, "/")}/.scratch/code-page-vscode-overhaul/sample-proj"))`);
for (let i = 0; i < 40; i++) {
  if (await Eval(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`)) break;
  await new Promise((r) => setTimeout(r, 300));
}
console.log("tree has big.c:", await Eval(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`));
console.log("tabs:", await Eval(`document.getElementById('code-tabs')?.innerText`));
await cdp("Runtime.enable", {});
await cdp("Runtime.evaluate", { expression: "window.__errs = []; window.addEventListener('error', e => window.__errs.push(e.message)); true" });
await Eval(`document.querySelector('#code-tree [data-code-file="big.c"]')?.click()`);
for (let i = 0; i < 60; i++) {
  const len = await Eval(`document.querySelector('#code-viewer .code-ta')?.value.length`);
  if (len) { console.log("ta len after " + (i * 500) + "ms:", len); break; }
  await new Promise((r) => setTimeout(r, 500));
}
console.log("viewer html head:", await Eval(`(document.getElementById('code-viewer')?.innerHTML || '').slice(0, 300)`));
console.log("ta len:", await Eval(`document.querySelector('#code-viewer .code-ta')?.value.length`));
console.log("console errors:", await Eval(`window.__errs ? window.__errs.join('|') : 'none'`));
process.exit(0);
