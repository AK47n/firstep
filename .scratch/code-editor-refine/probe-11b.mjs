// 探针 11b：分项计时——highlightCodeLines / gutter / fold visible+merge / marks
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
const stats = await Eval(`(async () => {
  const content = document.querySelector('#code-viewer .code-ta').value;
  const lines = content.split('\\n');
  const N = 6;
  const time = (fn) => { fn(); const t = performance.now(); for (let i = 0; i < N; i++) fn(); return ((performance.now() - t) / N).toFixed(2); };
  const cv = await import('/js/fx/codeview.js');
  const fold = await import('/js/fx/code-fold.js');
  const marks = await import('/js/fx/code-marks.js');
  const lang = 'c';
  const row = {};
  row.highlightAll = time(() => cv.highlightCodeLines(lines, lang));
  const folds = fold.codeFoldRanges(content, lang);
  const foldedSet = new Set(folds.filter(f => true).map(f => f.id));
  const vm = fold.codeFoldVisible(content, folds, foldedSet);
  row.foldVisible = time(() => fold.codeFoldVisible(content, folds, foldedSet));
  row.foldGutter = time(() => fold.codeFoldGutterLines(vm.lines));
  row.foldMerge = time(() => fold.codeFoldMerge(folds, foldedSet, folds));
  row.currentMarks = time(() => marks.currentMarks ? marks.currentMarks?.[0] : null) || 'n/a';
  row.marksHTML = time(() => marks.codeMarksHTML(content.slice(0, 4000), []));
  row.indentFull = time(() => marks.codeIndentGuideMarks(content));
  return row;
})()`);
console.log(JSON.stringify(stats, null, 2));
process.exit(0);
