// 复刻 v2：等待渲染完成 → 滚到 L44-68 → 几何 + 截图（用户视角）
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

// 等渲染：轮询直到 hl 行出现
for (let i = 0; i < 20; i++) {
  const n = await Eval(`document.querySelectorAll('#code-viewer .code-hl-line').length`);
  if (n > 10) break;
  await new Promise((r) => setTimeout(r, 300));
}
// 滚到 L44-68（视口行 44 起）
await Eval(`(() => {
  const box = document.getElementById('code-viewer');
  const first = document.querySelector('#code-viewer .code-hl-line[data-code-line="1"]');
  const lh = first ? first.getBoundingClientRect().height : 25;
  box.scrollTop = Math.max(0, (44 - 1) * lh);
  box.dispatchEvent(new Event('scroll', { bubbles: true }));
  return lh;
})()`);
await new Promise((r) => setTimeout(r, 500));

const out = await Eval(`(() => {
  const hlRows = [...document.querySelectorAll('#code-viewer .code-hl-line')];
  const mkRows = [...document.querySelectorAll('#code-viewer .code-marks-line')];
  const report = [];
  for (let i = 0; i < hlRows.length; i++) {
    const hl = hlRows[i], mk = mkRows[i];
    if (!mk) { report.push({ i, miss: 'mk' }); continue; }
    const n = parseInt(hl.dataset.codeLine, 10);
    if (n < 43 || n > 68) continue;
    const text = hl.textContent;
    const indent = text.match(/^[ \\t]*/)[0];
    const colWs = indent.replace(/\\t/g, '    ').length;
    const guides = [...mk.querySelectorAll('.code-mark-guide')].map((g) => {
      const r = g.getBoundingClientRect();
      return Math.round(r.left * 10) / 10;
    });
    report.push({ n, colWs, guides, textHead: text.slice(0, 22) });
  }
  return { report, hlCount: hlRows.length, mkCount: mkRows.length,
    firstHL: hlRows[0] ? hlRows[0].dataset.codeLine : null,
    zoom: document.getElementById('code-viewer').style.getPropertyValue('--code-zoom') };
})()`);
console.log("hl:", out.hlCount, "mk:", out.mkCount, "firstHL:", out.firstHL, "zoom:", out.zoom);
for (const r of out.report) console.log(`L${r.n} col=${r.colWs} guides=${JSON.stringify(r.guides)} | ${r.textHead}`);
const shot = await cdp("Page.captureScreenshot", { format: "png" });
const fs = await import("node:fs");
const p = "C:/Users/luoji/Desktop/firstep/.scratch/code-page-vscode-overhaul/shot-real-l44.png";
fs.writeFileSync(p, Buffer.from(shot.result.data, "base64"));
console.log("截图:", p);
process.exit(0);
