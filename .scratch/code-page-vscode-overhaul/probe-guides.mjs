// 诊断：当前页面 motor.c 的缩进引导线 vs 行首空白（空格/tab）实际分布。
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
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
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000/"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + JSON.stringify(r.result.exceptionDetails));
  return r.result?.result?.value;
};

const out = await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  if (!ta) return { err: 'no ta' };
  const lines = ta.value.split('\\n');
  const marks = [...document.querySelectorAll('#code-viewer .code-marks-line')];
  const hl = [...document.querySelectorAll('#code-viewer .code-hl-line')];
  const report = [];
  // 窗口内 30..76 行（用户截图范围）
  for (let n = 30; n <= 76; n++) {
    const line = lines[n - 1];
    if (line === undefined) continue;
    let ws = 0;
    while (ws < line.length && (line[ws] === ' ' || line[ws] === '\\t')) ws++;
    const head = line.slice(0, ws);
    const isTab = head.includes('\\t');
    const isSpace = head.includes(' ');
    const colWs = head.replace(/\\t/g, '    ').length;   // tab 展开 4 的列数
    // 该行 marks 层里的 guide span（按 data-code-line 匹配）
    const mi = n - 1;
    const guiders = marks[mi] ? [...marks[mi].querySelectorAll('.code-mark-guide')] : [];
    // guide span 的字符起始（从 marks 层 HTML 推断：span 前文本长度）
    const guideInfo = guiders.map((g) => {
      let idx = 0;
      let prev = g.previousSibling;
      // 直接量：marks line 的 textContent 长度到 span 前
      const before = [];
      let node = g.previousSibling;
      while (node) { before.unshift(node.textContent || ''); node = node.previousSibling; }
      return { at: before.join('').length, len: g.textContent.length };
    });
    report.push({ n, indent: JSON.stringify(head), isTab, isSpace, colWs, guides: guideInfo });
  }
  return { path: document.getElementById('code-breadcrumb')?.innerText, report: report.filter((r) => r.guides.length || r.isTab || r.colWs > 0).slice(0, 40) };
})()`);
console.log("path:", out.path);
for (const r of out.report) {
  console.log(`L${r.n} indent=${r.indent} tab=${r.isTab} col=${r.colWs} guides=${JSON.stringify(r.guides)}`);
}
process.exit(0);
