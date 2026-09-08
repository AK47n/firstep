// 验证修复：刷新 → 重新打开 2024H motor.c → 80% → 滚动 → 测 dy + 高清截图
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

// 刷新
await cdp("Page.reload", {});
await new Promise((r) => setTimeout(r, 2500));
// 重新打开
await Eval(`(async () => {
  const m = await import('/js/ui/codeview.js');
  m.openCodeViewer('C:\\\\Users\\\\luoji\\\\Desktop\\\\2024H_Auto_Car_MSPM0', 'modules/motor/code/motor.c');
  return true;
})()`);
await new Promise((r) => setTimeout(r, 1500));
// 80%
await Eval(`(() => { document.getElementById('code-viewer').style.setProperty('--code-zoom', '0.8'); return true; })()`);
await new Promise((r) => setTimeout(r, 300));
// 滚到 L44
await Eval(`(() => {
  const box = document.getElementById('code-viewer');
  const first = document.querySelector('#code-viewer .code-hl-line[data-code-line="1"]');
  const lh = first ? first.getBoundingClientRect().height : 25;
  box.scrollTop = Math.max(0, (44 - 1) * lh);
  box.dispatchEvent(new Event('scroll', { bubbles: true }));
  return lh;
})()`);
await new Promise((r) => setTimeout(r, 600));

const out = await Eval(`(() => {
  const hlRows = [...document.querySelectorAll('#code-viewer .code-hl-line')];
  const mkRows = [...document.querySelectorAll('#code-viewer .code-marks-line')];
  const rows = [];
  for (let i = 0; i < hlRows.length && i < mkRows.length; i++) {
    const n = parseInt(hlRows[i].dataset.codeLine, 10);
    if (n < 43 || n > 60) continue;
    const ry = hlRows[i].getBoundingClientRect();
    const gy = mkRows[i].getBoundingClientRect();
    rows.push({ n, dy: Math.round((gy.top - ry.top) * 10) / 10, guides: mkRows[i].querySelectorAll('.code-mark-guide').length });
  }
  return { rows, mkHead: document.querySelector('#code-viewer .code-marks')?.innerHTML.slice(0, 120) ?? '', hlHead: document.querySelector('#code-viewer .code-hl')?.innerHTML.slice(0, 120) ?? '' };
})()`);
console.log("mkHead:", out.mkHead);
console.log("hlHead:", out.hlHead);
for (const r of out.rows) console.log(`L${r.n} dy=${r.dy} guides=${r.guides}`);

// 高清截图
const rects = await Eval(`(() => {
  const a = document.querySelector('#code-viewer .code-hl-line[data-code-line="44"]');
  const b = document.querySelector('#code-viewer .code-hl-line[data-code-line="58"]');
  if (!a || !b) return null;
  const ra = a.getBoundingClientRect();
  const rb = b.getBoundingClientRect();
  return { x: Math.floor(ra.left - 40), y: Math.floor(ra.top - 20), w: Math.ceil(rb.right - ra.left) + 120, h: Math.ceil(rb.bottom - ra.top) + 40 };
})()`);
if (rects) {
  const shot = await cdp("Page.captureScreenshot", { format: "png", clip: { ...rects, scale: 2.5 } });
  const fs = await import("node:fs");
  const p = "C:/Users/luoji/Desktop/firstep/.scratch/code-page-vscode-overhaul/shot-fixed-guides.png";
  fs.writeFileSync(p, Buffer.from(shot.result.data, "base64"));
  console.log("高清截图:", p);
}
process.exit(0);
