// debug-ontrans：折叠 ON(200%) → setCell(100,true) 逐步状态
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
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => { const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }); if (r.result?.exceptionDetails) throw new Error("异常: " + JSON.stringify(r.result.exceptionDetails)); return r.result?.result?.value; };
const waitFor = async (expr, ms = 10000) => { for (let i = 0; i < ms / 200; i++) { try { if (await Eval(expr)) return true; } catch {} await new Promise((r) => setTimeout(r, 200)); } return false; };
const step = async (label, fn) => { try { const v = await Promise.race([fn(), new Promise((_, rej) => setTimeout(() => rej(new Error("TIMEOUT " + label)), 10000))]); console.log("OK", label, JSON.stringify(v)); return v; } catch (e) { console.log("ERR", label, e.message); } };
const foldState = () => Eval(`import('/js/ui/codeeditor.js').then((m) => ({ folded: m.editorViewText().includes('…'), ta: m.editorViewText().slice(0, 16) }))`);

await step("open viewer", () => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`));
await waitFor(`!!document.querySelector('#code-tree [data-code-file="bigfold.c"]')`);
await step("open bigfold", () => Eval(`document.querySelector('#code-tree [data-code-file="bigfold.c"]')?.click(); true`));
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);

const setCell = (themeIgnored, pct, fold) => Eval(`(async () => {
  const view = document.getElementById('code-viewer');
  view.style.setProperty('--code-zoom', String(${pct} / 100));
  const ce = await import('/js/ui/codeeditor.js');
  const log = [];
  const snap = () => ce.editorViewText().includes('…');
  ce.codeWindowRefresh();
  log.push(["refresh", snap()]);
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  const key = (k) => { ta.dispatchEvent(new KeyboardEvent('keydown', {
    key: k, code: k === '[' ? 'BracketLeft' : 'BracketRight',
    ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true }));
    log.push([k, snap(), JSON.parse(window.__dshFoldDbg || '{"key":"?"}')]); };
  key(']');
  ce.editJumpToLine(3005);
  log.push(["jump", snap()]);
  ${fold ? "key('[');" : ""}
  ta.focus();
  ta.setSelectionRange(0, 0);
  log.push(["sel", snap()]);
  window.__dshSetLog = JSON.stringify(log);
  return true;
})()`);

// 与 probe-04 相同的 12 格矩阵循环（只跑折叠有效性检查，不截图）
for (const theme of ["light", "dark"]) {
  for (const pct of [100, 150, 200]) {
    for (const fold of [false, true]) {
      await setCell(2000, pct, fold);   // 2000 = theme 忽略
      await new Promise((r) => setTimeout(r, 300));
      const real = await Eval(`import('/js/ui/codeeditor.js').then((m) => m.editorViewText().includes('…'))`);
      console.log("cell", theme, pct, fold, "foldReal=" + real, real === fold ? "OK" : "MISMATCH");
    }
  }
}
await step("state after matrix", foldState);
await step("13th: refresh", () => Eval(`(async () => { const v = document.getElementById('code-viewer'); v.style.setProperty('--code-zoom', '1'); const ce = await import('/js/ui/codeeditor.js'); ce.codeWindowRefresh(); return true; })()`));
await step("13th state after refresh", foldState);
await step("13th: key ]", () => Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.dispatchEvent(new KeyboardEvent('keydown', { key: ']', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true })); return true; })()`));
await step("13th state after ]", foldState);
await step("13th: jump 3005", () => Eval(`import('/js/ui/codeeditor.js').then((m) => { m.editJumpToLine(3005); return true; })`));
await new Promise((r) => setTimeout(r, 250));
await step("13th state after jump", foldState);
await step("13th: key [", () => Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.dispatchEvent(new KeyboardEvent('keydown', { key: '[', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true })); return true; })()`));
await new Promise((r) => setTimeout(r, 250));
await step("13th state after [", foldState);
await step("13th b: setCell 100 on AGAIN", () => setCell(2000, 100, true));
await new Promise((r) => setTimeout(r, 400));
await step("13th b log", () => Eval(`window.__dshSetLog`));
await step("fold dbg", () => Eval(`window.__dshFoldDbg`));
await step("state after 14th", foldState);
process.exit(0);
await step("setCell 200 on", () => setCell(200, true));
await new Promise((r) => setTimeout(r, 350));
await step("state 200 on", foldState);
// 逐步模拟 13th：refresh → key(']') → jump → key('[') —— 每步查折叠
await step("refresh 100", () => Eval(`(async () => {
  const view = document.getElementById('code-viewer');
  view.style.setProperty('--code-zoom', '1');
  const ce = await import('/js/ui/codeeditor.js');
  ce.codeWindowRefresh();
  return true;
})()`));
await step("state after refresh", foldState);
await step("key ]", () => Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.dispatchEvent(new KeyboardEvent('keydown', { key: ']', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true })); return true; })()`));
await step("state after ]", foldState);
await step("jump 3005", () => Eval(`import('/js/ui/codeeditor.js').then((m) => { m.editJumpToLine(3005); return true; })`));
await new Promise((r) => setTimeout(r, 250));
await step("state after jump", foldState);
await step("key [", () => Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.dispatchEvent(new KeyboardEvent('keydown', { key: '[', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true })); return true; })()`));
await new Promise((r) => setTimeout(r, 250));
await step("state after [", foldState);
process.exit(0);
