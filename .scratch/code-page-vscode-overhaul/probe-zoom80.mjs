// 复现实验：headless 设 --code-zoom=0.8（80%）→ 几何测量 + 截图
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

// 设 80%
await Eval(`(() => {
  const view = document.getElementById('code-viewer');
  view.style.setProperty('--code-zoom', '0.8');
  view.dispatchEvent(new Event('resize'));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 500));

const out = await Eval(`(() => {
  const hlRows = [...document.querySelectorAll('#code-viewer .code-hl-line')];
  const mkRows = [...document.querySelectorAll('#code-viewer .code-marks-line')];
  const report = [];
  for (let i = 0; i < hlRows.length; i++) {
    const hl = hlRows[i], mk = mkRows[i];
    if (!mk) continue;
    const n = parseInt(hl.dataset.codeLine, 10);
    if (n < 43 || n > 68) continue;
    const text = hl.textContent;
    const indent = text.match(/^[ \\t]*/)[0];
    const colWs = indent.replace(/\\t/g, '    ').length;
    const guides = [...mk.querySelectorAll('.code-mark-guide')].map((g) => {
      const r = g.getBoundingClientRect();
      return Math.round(r.left * 10) / 10;
    });
    const mkText = mk.textContent;
    const indentMk = mkText.match(/^[ \\t]*/)[0];
    report.push({ n, colWs, guides, mkIndentLen: indentMk.length, textHead: text.slice(0, 16) });
  }
  return report;
})()`);
for (const r of out) console.log(`L${r.n} col=${r.colWs} guides=${JSON.stringify(r.guides)} mkIndentLen=${r.mkIndentLen} | ${r.textHead}`);
const shot = await cdp("Page.captureScreenshot", { format: "png" });
const fs = await import("node:fs");
const p = "C:/Users/luoji/Desktop/firstep/.scratch/code-page-vscode-overhaul/shot-zoom80.png";
fs.writeFileSync(p, Buffer.from(shot.result.data, "base64"));
console.log("截图:", p);
process.exit(0);
