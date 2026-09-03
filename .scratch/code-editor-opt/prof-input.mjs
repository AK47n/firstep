// 探针（code-editor-opt 诊断）：6000 行 .c 单次 input 事件 CPU 采样
// ——Profiler.start/stop 聚合自耗时，定位逐键热点的函数级分布。
// CDP 9251 + webapp 8000；零写库。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-opt");
const SAMPLE = join(ROOT, ".scratch", "code-editor-refine", "sample-proj-11");
mkdirSync(OUT, { recursive: true });

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
const waitFor = async (expr, ms = 12000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};

await Eval(`window.__probe = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100; i++) {
  try {
    if (await Eval(`document.readyState === 'complete' && !window.__probe && !!document.getElementById('code-viewer')`)) break;
  } catch {}
  await new Promise((r) => setTimeout(r, 300));
}
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="big.c"]').click(); true`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);

// 预热一次输入（结构/缓存已就位）
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value + 'y';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  ta.value = ta.value.slice(0, -1);
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);

await cdp("Profiler.enable");
const t0 = Date.now();
await cdp("Profiler.start");
const timing = await Eval(`(async () => {
  const ta = document.querySelector('#code-viewer .code-ta');
  const before = ta.value;
  const t = performance.now();
  ta.value = before + 'x';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  const ms = performance.now() - t;
  ta.value = before;
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return ms;
})()`);
const prof = (await cdp("Profiler.stop")).result.profile;
console.log("input 事件耗时(ms):", timing.toFixed(2), "采样时长(ms):", Date.now() - t0);

// 聚合自耗时：按 functionName + url 分组
const nodes = new Map();
for (const n of prof.nodes) nodes.set(n.id, n);
const self = new Map();
const counts = new Map();
for (let i = 0; i < prof.samples.length; i++) {
  const id = prof.samples[i];
  const n = nodes.get(id);
  if (!n) continue;
  const name = n.callFrame.functionName || "(anonymous)";
  const url = n.callFrame.url || "";
  const key = name + " @ " + url.split("/").pop();
  self.set(key, (self.get(key) || 0) + (prof.timeDeltas[i] || 0));
  counts.set(key, (counts.get(key) || 0) + 1);
}
const rows = [...self.entries()].map(([k, v]) => ({ fn: k, ms: (v / 1000).toFixed(2), samples: counts.get(k) }))
  .sort((a, b) => b.samples - a.samples).slice(0, 25);
console.table(rows);
writeFileSync(join(OUT, "prof-input.json"), JSON.stringify({ timing, rows }, null, 2));
process.exit(0);
