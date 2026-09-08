// debug-move：折叠态 setCaret(3) + Alt+ArrowUp —— 逐步 dump
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

await step("open viewer", () => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`));
await waitFor(`!!document.querySelector('#code-tree [data-code-file="bigfold.c"]')`);
await step("open bigfold", () => Eval(`document.querySelector('#code-tree [data-code-file="bigfold.c"]')?.click(); true`));
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
await step("jump 3005", () => Eval(`import('/js/ui/codeeditor.js').then((m) => { m.editJumpToLine(3005); return true; })`));
await new Promise((r) => setTimeout(r, 250));
await step("fold", () => Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.dispatchEvent(new KeyboardEvent('keydown', { key: '[', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true })); return true; })()`));
await waitFor(`document.querySelector('#code-viewer .code-ta').value.includes('…')`);
await step("setCaret 3", () => Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.setSelectionRange(3, 3); return [ta.selectionStart, ta.selectionEnd]; })()`));
await step("editSource probe", () => Eval(`window.__dshEditSource ? window.__dshEditSource() : 'no'`));
await step("viewText head", () => Eval(`import('/js/ui/codeeditor.js').then((m) => m.editorViewText().slice(0, 20))`));
const region = () => Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const m = ce.getActiveTab().content;
  return m.slice(88400, 88540);
})()`);
await step("region before", region);
await step("press Alt+Up", () => Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', altKey: true, bubbles: true, cancelable: true })); return true; })()`));
await new Promise((r) => setTimeout(r, 250));
await step("diag", () => Eval(`({ hit: window.__dshDiag || 0, info: window.__dshDiag2 || 'none', info3: window.__dshDiag3 || 'none' })`));
await step("region after", region);
await step("post-move state", () => Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const m = ce.getActiveTab().content;
  return { modelHead: m.slice(0, 30), modelLen: m.length, view: ce.editorViewText().slice(88300, 88460) };
})()`));
await step("pure chain probe", () => Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const lp = await import('/js/fx/code-lineops.js');
  const cf = await import('/js/fx/code-fold.js');
  const ta = document.querySelector('#code-viewer .code-ta');
  const m = ce.getActiveTab().content;
  const vs = ce.editorViewText();
  const winFirst = ta.value.slice(0, 12);
  const viewSel = vs.indexOf(winFirst) + 3;
  const r = lp.moveLine(vs, viewSel, viewSel, 'up');
  const folds = cf.codeFoldRanges(m, 'c');
  const vm = cf.codeFoldVisible(m, folds, new Set([0]));
  const r2 = cf.codeFoldMapEdit(m, vm.segs, vm.text, r.value);
  return { r: r.value === vs, mapChanged: r2.model !== m,
    mapCaret: r2.caret, expand: r2.expand.length, vmSegs: vm.segs.length };
})()`));
process.exit(0);
