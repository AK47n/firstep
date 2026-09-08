// 验证滚动态可点击性：elementFromPoint 在可视区内多点（行 12/20/30 位置处）
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
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
const d = await Eval(`(() => {
  const box = document.getElementById('code-viewer');
  const br = box.getBoundingClientRect();
  const ta = document.querySelector('#code-viewer .code-ta');
  const tr = ta.getBoundingClientRect();
  // 行矩形：按 hl-line 逐个取，找可视区内的行
  const lines = Array.from(document.querySelectorAll('#code-viewer .code-hl-line'));
  const info = [];
  for (const ln of lines) {
    const no = Number(ln.dataset.codeLine);
    const r = ln.getBoundingClientRect();
    if (r.top >= br.top && r.top < br.bottom) {
      const el = document.elementFromPoint(Math.min(700, box.getBoundingClientRect().right - 30), r.top + r.height / 2);
      info.push({ no: no, visible: true, el: el ? (el.className || el.tagName) : null, isTa: !!el && el.classList.contains('code-ta') });
    }
  }
  return {
    boxTop: Math.round(br.top), boxBottom: Math.round(br.bottom),
    taTop: Math.round(tr.top), taBottom: Math.round(tr.bottom),
    taH: Math.round(tr.height),
    visible: info,
    sample: info.slice(0, 3).concat(info.slice(-3)),
  };
})()`);
console.log(JSON.stringify(d, null, 2));
process.exit(0);
