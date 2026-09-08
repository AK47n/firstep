// debug-shot：bigfold 折叠后 49% 滚动——折叠是否保持 + 窗口内容
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const SAMPLE = join(ROOT, ".scratch", "editor-textarea-viewport", "sample-proj");
const CDP = 9251, pageUrl = "http://127.0.0.1:8000/";
const fetchT = async (url, ms = 5000) => { const c = new AbortController(); const t = setTimeout(() => c.abort(), ms); try { return await fetch(url, { signal: c.signal }); } finally { clearTimeout(t); } };
let targets = null;
for (let i = 0; i < 50 && !targets; i++) { try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {} if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300)); }
const page = targets.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } else if (m.method === "Page.javascriptDialogOpening") { const id = ++seq; pending.set(id, () => {}); ws.send(JSON.stringify({ id, method: "Page.handleJavaScriptDialog", params: { accept: true } })); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => { const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }); if (r.result?.exceptionDetails) throw new Error("异常: " + JSON.stringify(r.result.exceptionDetails)); return r.result?.result?.value; };
const waitFor = async (expr, ms = 10000) => { for (let i = 0; i < ms / 200; i++) { try { if (await Eval(expr)) return true; } catch {} await new Promise((r) => setTimeout(r, 200)); } return false; };
const step = async (label, fn) => { try { const v = await Promise.race([fn(), new Promise((_, rej) => setTimeout(() => rej(new Error("TIMEOUT " + label)), 10000))]); console.log("OK", label, JSON.stringify(v)); return v; } catch (e) { console.log("ERR", label, e.message); } };
const state = () => Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const ta = document.querySelector('#code-viewer .code-ta');
  const b = document.getElementById('code-viewer');
  return { folded: ce.editorViewText().includes('…'), taHead: ta.value.slice(0, 26),
    gutHead: Array.from(document.querySelectorAll('.code-gutter-line')).slice(0, 3).map((e) => e.dataset.codeLine),
    scrollTop: b.scrollTop, scrollH: b.scrollHeight, winHasPh: ta.value.includes('…') };
})()`);

await step("open viewer", () => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`));
await waitFor(`!!document.querySelector('#code-tree [data-code-file="bigfold.c"]')`);
await step("open bigfold", () => Eval(`document.querySelector('#code-tree [data-code-file="bigfold.c"]')?.click(); true`));
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
const setCell = (pct, fold) => Eval(`(async () => {
  const view = document.getElementById('code-viewer');
  view.style.setProperty('--code-zoom', String(${pct} / 100));
  const ce = await import('/js/ui/codeeditor.js');
  ce.codeWindowRefresh();
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  const key = (k) => ta.dispatchEvent(new KeyboardEvent('keydown', {
    key: k, code: k === '[' ? 'BracketLeft' : 'BracketRight',
    ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true }));
  key(']');
  ce.editJumpToLine(3005);
  ${fold ? "key('[');" : ""}
  ta.focus();
  ta.setSelectionRange(0, 0);
  return true;
})()`);
await step("setCell 100 fold", () => setCell(100, true));
await new Promise((r) => setTimeout(r, 400));
await step("state after fold", state);
await step("scroll 49%", () => Eval(`(() => { const b = document.getElementById('code-viewer'); b.scrollTop = Math.floor(b.scrollHeight * 0.49); b.dispatchEvent(new Event('scroll')); return true; })()`));
await new Promise((r) => setTimeout(r, 400));
await step("state after scroll", state);
process.exit(0);
