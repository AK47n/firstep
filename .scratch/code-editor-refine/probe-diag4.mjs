// 检查打开 beep.c 后的状态
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
console.log("tabs:", JSON.stringify(await Eval(`Array.from(document.querySelectorAll('#code-tabs .code-tab')).map(t => t.dataset.tabPath + '|' + t.textContent.slice(0,20))`)));
console.log("pane html 前 400:", JSON.stringify(await Eval(`document.querySelector('#code-viewer')?.innerHTML.slice(0, 400)`)));
console.log("dir label:", JSON.stringify(await Eval(`document.querySelector('#code-dir-label')?.textContent.slice(0,120)`)));
const r = await Eval(`import('/js/ui/codeeditor.js').then((m) => m.openEditorFile('modules/beep/code/beep.c')).then(() => 'ok').catch((e) => 'ERR:' + e.message)`);
console.log("openEditorFile:", JSON.stringify(r));
await new Promise((res) => setTimeout(res, 1500));
console.log("tabs2:", JSON.stringify(await Eval(`Array.from(document.querySelectorAll('#code-tabs .code-tab')).map(t => t.dataset.tabPath + '|' + t.textContent.slice(0,20))`)));
console.log("pane2 前 300:", JSON.stringify(await Eval(`document.querySelector('#code-viewer')?.innerHTML.slice(0, 300)`)));
process.exit(0);
