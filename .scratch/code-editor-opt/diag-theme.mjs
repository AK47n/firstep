// 诊断（code-editor-opt）：运行时 dark→light 切换后 --input-bg 到底是多少
import { mkdirSync } from "node:fs";
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
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const msg = JSON.parse(ev.data); if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); } };
const cdp = (m, p = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
await Eval(`document.documentElement.setAttribute('data-theme','light'); localStorage.setItem('firstep.theme','light'); true`);
await new Promise((r) => setTimeout(r, 300));
const out = await Eval(`(() => {
  const rootVar = getComputedStyle(document.documentElement).getPropertyValue('--input-bg');
  const filter = document.getElementById('code-outline-filter');
  const probe = document.createElement('input');
  probe.type = 'text';
  document.body.appendChild(probe);
  const r = {
    attr: document.documentElement.getAttribute('data-theme'),
    rootVar: rootVar.trim(),
    filterBg: filter ? getComputedStyle(filter).backgroundColor : null,
    probeBg: getComputedStyle(probe).backgroundColor,
  };
  probe.remove();
  return r;
})()`);
console.log(JSON.stringify(out, null, 2));
process.exit(0);
