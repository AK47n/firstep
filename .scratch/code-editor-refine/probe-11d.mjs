// 探针 11d：真实击键路径（execCommand insertText，applyEdit 同路径）测输入处理
// ——在行中部插入单字符，measure dispatch 同步耗时 x8 取均值；对比 value 重写。
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
const out = await Eval(`(async () => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  // 光标移到中部（第 3000 行附近）
  const v = ta.value;
  let pos = 0; let lines = 0;
  for (let i = 0; i < v.length && lines < 3000; i++) { if (v[i] === '\\n') lines++; pos = i; }
  ta.setSelectionRange(pos, pos);
  const times = [];
  for (let k = 0; k < 8; k++) {
    const t0 = performance.now();
    try {
      document.execCommand('insertText', false, 'z');
    } catch (e) { /* 某些环境禁用 */ }
    const dt = performance.now() - t0;
    times.push(dt.toFixed(1));
    // 撤销回去（保持文件不变）
    document.execCommand('undo');
  }
  return { avg: (times.reduce((a, b) => a + parseFloat(b), 0) / times.length).toFixed(2), times };
})()`);
console.log(JSON.stringify(out, null, 2));
process.exit(0);
