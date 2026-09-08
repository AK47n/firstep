// 验证：折叠态光标→高亮对齐（gutter 模型号 vs hl 视图号）
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
const waitFor = async (expr, ms = 10000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};
const DIR = "C:\\Users\\luoji\\Desktop\\2024H_Auto_Car_MSPM0";
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(DIR)}))`);
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.openEditorFile('modules/beep/code/beep.c'))`);
const opened = await waitFor(`!!document.querySelector('#code-viewer .code-ta')`, 5000);
if (!opened) {
  console.log("未打开，现场:", JSON.stringify(await Eval(`(() => ({
    label: document.querySelector('#code-dir-label')?.textContent.slice(0, 90),
    pane: document.querySelector('#code-viewer')?.innerHTML.slice(0, 220),
    tabs: Array.from(document.querySelectorAll('#code-tabs .code-tab')).map(t => t.dataset.tabPath),
  }))()`)));
  process.exit(0);
}
// 折叠第一个可折叠块：光标放到 void beep_on 行 → Ctrl+Shift+[
// 折叠第一个可折叠块：先制造结构编辑（换行 → folds 重算），光标放行 11 → Ctrl+Shift+[
const seeded = await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value + '\\n// seed';   // 结构编辑（新增换行 → sync 重算 folds）
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
console.log("seed:", JSON.stringify(seeded));
await new Promise((r) => setTimeout(r, 500));
const folded = await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  if (!ta) return { ok: false, why: 'no-ta' };
  const lines = ta.value.split('\\n');
  let pos = 0;
  for (let i = 0; i < 10; i++) pos += lines[i].length + 1;   // 行 11 起点
  ta.focus();
  ta.setSelectionRange(pos, pos);
  ta.dispatchEvent(new KeyboardEvent('keydown', { key: '[', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true }));
  return { ok: true };
})()`);
console.log("fold:", JSON.stringify(folded));
await new Promise((r) => setTimeout(r, 600));
const foldState = await Eval(`(() => ({
  arrows: document.querySelectorAll('#code-viewer .code-fold-arrow').length,
  phs: document.querySelectorAll('#code-viewer .code-gutter-ph').length,
}))()`);
console.log("foldState:", JSON.stringify(foldState));
// 光标移到视图第 10 行（第 1 个可见行），触发 select 高亮
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  const lines = ta.value.split('\\n');
  let pos = 0;
  for (let i = 0; i < 9; i++) pos += lines[i].length + 1;
  ta.focus();
  ta.setSelectionRange(pos, pos);
  ta.dispatchEvent(new Event('select', { bubbles: true }));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 400));
const d = await Eval(`(() => {
  const gutA = document.querySelector('#code-viewer .code-gutter-line.active');
  const hlA = document.querySelector('#code-viewer .code-hl-line.active');
  const ta = document.querySelector('#code-viewer .code-ta');
  return {
    foldArrows: document.querySelectorAll('#code-viewer .code-fold-arrow').length,
    gutActive: gutA ? Number(gutA.dataset.codeLine) : null,
    hlActive: hlA ? Number(hlA.dataset.codeLine) : null,
    caretViewLine: (() => { let c = 0; const v = ta.value; for (let i = 0; i < ta.selectionStart; i++) if (v[i] === '\\n') c++; return c + 1; })(),
    taViewLines: ta.value.split('\\n').length,
    gutFirst: Number(document.querySelector('#code-viewer .code-gutter-line')?.dataset.codeLine),
    gutLast: Number(Array.from(document.querySelectorAll('#code-viewer .code-gutter-line')).pop()?.dataset.codeLine),
  };
})()`);
console.log(JSON.stringify(d, null, 2));
process.exit(0);
