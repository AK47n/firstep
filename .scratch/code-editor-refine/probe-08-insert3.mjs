// 探针 3：click 是否到达 #code-ai-chat-body + 捕获层情况
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
};
let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetchT("http://127.0.0.1:9251/json/list")).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000/"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const msg = JSON.parse(ev.data); if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); } };
const cdp = (m, p = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { err: r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails) };
  return r.result?.result?.value;
};
console.log("挂计数:", await Eval(`(() => {
  window.__clicks = 0; window.__bodyClicks = 0; window.__capClicks = 0;
  const body = document.getElementById('code-ai-chat-body');
  body.addEventListener('click', () => { window.__bodyClicks++; }, true);
  document.addEventListener('click', () => { window.__capClicks++; }, true);
  document.addEventListener('click', () => { window.__clicks++; });
  return true;
})()`));
console.log("点击按钮:", await Eval(`document.querySelector('[data-ai-insert]').click(); true`));
await new Promise((r) => setTimeout(r, 300));
console.log("计数:", await Eval(`({body: window.__bodyClicks, cap: window.__capClicks, all: window.__clicks})`));
console.log("toast:", await Eval(`document.getElementById('toast-root')?.textContent || ''`));
process.exit(0);
