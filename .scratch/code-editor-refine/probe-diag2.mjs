// 诊断：当前页面 beep.c 状态——.code-edit 高度 vs 行数 / 缩放 / gutter 与 hl 行数
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
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
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
const d = await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  const edit = document.querySelector('#code-viewer .code-edit');
  const hl = document.querySelector('#code-viewer .code-hl');
  const gutter = document.querySelector('#code-viewer .code-gutter');
  const box = document.getElementById('code-viewer');
  const activeTab = document.querySelector('#code-tabs .code-tab.on');
  const zoom = document.querySelector('#code-zoom-badge')?.textContent || document.querySelector('.code-zoom-badge')?.textContent || '';
  const r = (el) => el ? { w: Math.round(el.getBoundingClientRect().width), h: Math.round(el.getBoundingClientRect().height), top: Math.round(el.getBoundingClientRect().top) } : null;
  return {
    url: location.href,
    activeTab: activeTab ? activeTab.dataset.tabPath : null,
    tabText: activeTab ? activeTab.textContent.slice(0, 60) : '',
    ta: r(ta), edit: r(edit), hl: r(hl), gutter: r(gutter), box: r(box),
    editStyle: edit ? { h: edit.style.height, w: edit.style.width, fontSize: getComputedStyle(edit).fontSize } : null,
    taStyle: ta ? { color: getComputedStyle(ta).color, bg: getComputedStyle(ta).backgroundColor } : null,
    taLines: ta ? ta.value.split('\\n').length : 0,
    hlChildren: hl ? hl.children.length : 0,
    hlInlineCount: hl ? hl.querySelectorAll('.code-hl-line').length : 0,
    gutterChildren: gutter ? gutter.children.length : 0,
    gutterLines: gutter ? gutter.querySelectorAll('.code-gutter-line').length : 0,
    gutterPh: gutter ? gutter.querySelectorAll('.code-gutter-ph').length : 0,
    marksLines: document.querySelectorAll('#code-viewer .code-marks .code-marks-line').length,
    zoomBadge: zoom,
    scrollTop: box ? box.scrollTop : -1,
    overflow: edit ? getComputedStyle(edit).overflow : '',
  };
})()`);
console.log(JSON.stringify(d, null, 2));
process.exit(0);
