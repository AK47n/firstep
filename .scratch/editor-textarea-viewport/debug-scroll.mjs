// 调试：滚动后 textarea 窗口是否同步（02 现场排查）
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
await Eval(`document.querySelector('#code-tree [data-code-file="big.c"]').click(); true`);
await new Promise((r) => setTimeout(r, 500));
const before = await Eval(`(() => { const box=document.getElementById('code-viewer'); const ta=box.querySelector('.code-ta');
  return { scrollTop: box.scrollTop, top: ta.style.top, h: ta.style.height, taLen: ta.value.length, clientH: box.clientHeight }; })()`);
console.log("before:", JSON.stringify(before));
await Eval(`(() => { const box=document.getElementById('code-viewer'); box.scrollTop = Math.floor(box.scrollHeight * 0.5); return true; })()`);
await new Promise((r) => setTimeout(r, 800));
const after = await Eval(`(() => { const box=document.getElementById('code-viewer'); const ta=box.querySelector('.code-ta'); const sp=box.querySelector('.code-hl .code-window-spacer');
  return { scrollTop: box.scrollTop, top: ta.style.top, h: ta.style.height, taLen: ta.value.length,
    spacerH: sp ? sp.style.height : null, clientH: box.clientHeight,
    winLast: (() => { try { return null; } catch(e){ return e.message; } })() }; })()`);
console.log("after:", JSON.stringify(after));
process.exit(0);
