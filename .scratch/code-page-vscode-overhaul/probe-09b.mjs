// 09 探针 2：CDP Profiler 抓单次输入同步的热点。
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-page-vscode-overhaul", "sample-proj");
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
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + JSON.stringify(r.result.exceptionDetails));
  return r.result?.result?.value;
};
await cdp("Profiler.enable", {});
await Eval(`window.__smokeMarker = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100; i++) {
  if (await Eval(`document.readyState === 'complete' && !window.__smokeMarker && !!document.getElementById('code-viewer')`)) break;
  await new Promise((r) => setTimeout(r, 300));
}
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
for (let i = 0; i < 40; i++) {
  if (await Eval(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`)) break;
  await new Promise((r) => setTimeout(r, 300));
}
await Eval(`document.querySelector('#code-tree [data-code-file="big.c"]')?.click()`);
for (let i = 0; i < 60; i++) {
  if (await Eval(`(document.querySelector('#code-viewer .code-ta')?.value.length || 0) > 100000`)) break;
  await new Promise((r) => setTimeout(r, 500));
}
await cdp("Profiler.start", {});
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
  ta.value += 'xy';
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  return true;
})()`);
const prof = await cdp("Profiler.stop", {});
await cdp("Profiler.disable", {});
const nodes = prof.result?.profile?.nodes || [];
const samples = prof.result?.profile?.samples || [];
const times = prof.result?.profile?.timeDeltas || [];
const selfTime = new Map();
for (let i = 0; i < samples.length; i++) {
  const id = samples[i];
  const dt = times[i] || 0;
  selfTime.set(id, (selfTime.get(id) || 0) + dt);
}
const rows = [...selfTime.entries()].map(([id, t]) => {
  const n = nodes.find((x) => x.id === id);
  return { name: n?.callFrame?.functionName || "(anon)", url: (n?.callFrame?.url || "").split("/").pop(), line: n?.callFrame?.lineNumber, t: t / 1000 };
}).sort((a, b) => b.t - a.t).slice(0, 60);
const agg = new Map();
for (const r of rows) {
  const k = r.name + "@" + r.url + ":" + r.line;
  agg.set(k, (agg.get(k) || 0) + r.t);
}
console.table([...agg.entries()].map(([k, t]) => ({ fn: k, ms: t.toFixed(1) })).sort((a, b) => b.ms - a.ms).slice(0, 30));
process.exit(0);
