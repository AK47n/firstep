// 探针：smoke-08 4c——选区替换为何未生效
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
  if (r.result?.exceptionDetails) return { err: r.result.exceptionDetails.exception?.description || "?" };
  return r.result?.result?.value;
};
console.log("初始前 40 字:", await Eval(`document.querySelector('#code-viewer .code-ta').value.slice(0,40)`));
await Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.setSelectionRange(0,15); ta.dispatchEvent(new Event('mouseup',{bubbles:true})); return [ta.selectionStart, ta.selectionEnd]; })()`);
console.log("选区:", await Eval(`(() => { const ta=document.querySelector('#code-viewer .code-ta'); return [ta.selectionStart, ta.selectionEnd]; })()`));
console.log("按钮数:", await Eval(`document.querySelectorAll('[data-ai-insert]').length`));
const r = await Eval(`document.querySelector('[data-ai-insert]')?.click(); 'clicked'`);
console.log("点击:", JSON.stringify(r));
await new Promise((res) => setTimeout(res, 500));
console.log("后 40 字:", await Eval(`document.querySelector('#code-viewer .code-ta').value.slice(0,40)`));
console.log("occurrences:", await Eval(`document.querySelector('#code-viewer .code-ta').value.split('int addOne = 0;').length - 1`));
process.exit(0);
