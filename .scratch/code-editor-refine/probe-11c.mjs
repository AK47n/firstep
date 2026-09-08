// 探针 11c：Profiler 采样 3 次输入事件，输出自耗时 Top 函数
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
await cdp("Profiler.enable");
await cdp("Profiler.setSamplingInterval", { interval: 500 });
await cdp("Profiler.start");
await Eval(`(async () => {
  const ta = document.querySelector('#code-viewer .code-ta');
  const b = ta.value;
  for (let k = 0; k < 3; k++) {
    ta.value = b + 'x' + k;
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    ta.value = b;
    ta.dispatchEvent(new Event('input', { bubbles: true }));
  }
  return true;
})()`);
await new Promise((r) => setTimeout(r, 300));
const stopRes = await cdp("Profiler.stop");
const profile = stopRes.result.profile;
// 聚合自耗时（node 级）
const nodes = new Map(profile.nodes.map((n) => [n.id, n]));
const self = new Map();
for (const n of profile.nodes) {
  const nm = (n.callFrame.functionName || "(anon)");
  const key = nm + " @ " + (n.callFrame.url || "").split("/").pop();
  self.set(key, (self.get(key) || 0) + (n.hitCount || 0));
}
const top = [...self.entries()].sort((a, b) => b[1] - a[1]).slice(0, 22);
const total = [...self.values()].reduce((a, b) => a + b, 0);
console.log("samples:", total);
for (const [k, v] of top) console.log(String(v).padStart(5), (100 * v / total).toFixed(1) + "%", k);
process.exit(0);
