// 诊断 v2：检查当前页面代码查看器 DOM 结构与 textarea 内容
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
const CDP = 9251;
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
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000/"));
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

const out = await Eval(`(() => {
  const info = {};
  info.breadcrumb = document.getElementById('code-breadcrumb')?.innerText ?? null;
  const viewer = document.getElementById('code-viewer');
  info.viewer = !!viewer;
  const ta = viewer?.querySelector('.code-ta');
  info.taFound = !!ta;
  info.taValLen = ta?.value?.length ?? -1;
  info.taFirstLine = ta?.value?.split('\\n')[0] ?? null;
  // 所有 .code-ta 候选
  info.allTa = [...document.querySelectorAll('textarea')].map((t) => ({ cls: t.className, len: t.value.length }));
  // marks/pre 层结构
  const preEls = [...document.querySelectorAll('#code-viewer pre, #code-viewer .code-marks')];
  info.pres = preEls.map((p) => ({ cls: p.className, childCount: p.childElementCount, firstClass: p.firstElementChild?.className ?? null, lastClass: p.lastElementChild?.className ?? null }));
  info.marksLines = document.querySelectorAll('#code-viewer .code-marks-line').length;
  info.hlLines = document.querySelectorAll('#code-viewer .code-hl-line').length;
  info.marksHTMLHead = (document.querySelector('#code-viewer .code-marks')?.innerHTML ?? '').slice(0, 300);
  return info;
})()`);
console.log(JSON.stringify(out, null, 2));
process.exit(0);
