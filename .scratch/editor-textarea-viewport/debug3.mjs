// 调试3：检查 #code-viewer 是否被重建（scroll 监听挂死假设）
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "editor-textarea-viewport", "sample-proj");
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
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const msg = JSON.parse(ev.data); if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); } };
const cdp = (m, p = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
await Eval(`window.__probe = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100; i++) {
  try { if (await Eval(`document.readyState === 'complete' && !window.__probe && !!document.getElementById('code-viewer')`)) break; } catch {}
  await new Promise((r) => setTimeout(r, 300));
}
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
for (let i = 0; i < 40; i++) { try { if (await Eval(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`)) break; } catch {} await new Promise((r) => setTimeout(r, 200)); }
const cnt = await Eval(`document.querySelectorAll('#code-viewer').length`);
console.log("cnt before open:", cnt);
await Eval(`document.querySelector('#code-tree [data-code-file="big.c"]').click(); true`);
await new Promise((r) => setTimeout(r, 500));
const cnt2 = await Eval(`document.querySelectorAll('#code-viewer').length`);
const info = await Eval(`(() => {
  const nodes = document.querySelectorAll('#code-viewer');
  const out = [];
  nodes.forEach((n) => {
    const ta = n.querySelector('.code-ta');
    const r = n.getBoundingClientRect();
    out.push({ connected: n.isConnected, rectTop: r.top, h: r.height, hasTa: !!ta, parentId: n.parentElement ? n.parentElement.id : null });
  });
  return out;
})()`);
console.log("cnt after open:", cnt2);
console.log("nodes:", JSON.stringify(info));
process.exit(0);
