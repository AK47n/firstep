// 精确几何测量 v2：hl 行与 marks 行按 DOM 顺序配对（同 index），
// 全量行号取自 hl 行 data-code-line；对比每行 guide span 实测 x vs 期望列 x。
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
  const hlRows = [...document.querySelectorAll('#code-viewer .code-hl-line')];
  const mkRows = [...document.querySelectorAll('#code-viewer .code-marks-line')];
  const report = [];
  for (let i = 0; i < hlRows.length; i++) {
    const hl = hlRows[i];
    const mk = mkRows[i];
    if (!mk) continue;
    const n = parseInt(hl.dataset.codeLine, 10);
    if (n < 27 || n > 84) continue;
    const text = hl.textContent;
    const indent = text.match(/^[ \\t]*/)[0];
    const colWs = indent.replace(/\\t/g, '    ').length;
    const mkText = mk.textContent;
    const indentMk = mkText.match(/^[ \\t]*/)[0];
    const guides = [...mk.querySelectorAll('.code-mark-guide')].map((g) => {
      const r = g.getBoundingClientRect();
      return Math.round(r.left * 10) / 10;
    });
    report.push({ n, colWs, indent: JSON.stringify(indent), textHead: text.slice(0, 24), mkIndent: JSON.stringify(indentMk), guides });
  }
  return report;
})()`);
for (const r of out) {
  console.log(`L${r.n} col=${r.colWs} guides=${JSON.stringify(r.guides)} | hl="${r.textHead}" mkIndent=${r.mkIndent}`);
}
const shot = await cdp("Page.captureScreenshot", { format: "png" });
const fs = await import("node:fs");
const shotPath = "C:/Users/luoji/Desktop/firstep/.scratch/code-page-vscode-overhaul/shot-current-view.png";
fs.writeFileSync(shotPath, Buffer.from(shot.result.data, "base64"));
console.log("截图:", shotPath);
process.exit(0);
