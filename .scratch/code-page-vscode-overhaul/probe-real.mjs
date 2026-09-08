// 完全复刻用户路径：openCodeViewer(2024H 工程, motor.c) + 80% → 几何 + 截图
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

// 真实打开
const opened = await Eval(`(async () => {
  try {
    const m = await import('/js/ui/codeview.js');
    m.openCodeViewer('C:\\\\Users\\\\luoji\\\\Desktop\\\\2024H_Auto_Car_MSPM0', 'modules/motor/code/motor.c');
    return 'ok';
  } catch (e) { return 'err:' + (e && e.message); }
})()`);
console.log("openCodeViewer:", opened);
await new Promise((r) => setTimeout(r, 1200));

// 80% 缩放（偷 api：directly set var + 触发滚轮事件路径太重；直接 set + 手动触发窗口刷新）
await Eval(`(() => {
  const view = document.getElementById('code-viewer');
  view.style.setProperty('--code-zoom', '0.8');
  return true;
})()`);
// 缩放后 winLineH 需重测 —— 触发 codeWindowRefresh 不可达单例？codeview.js export applyCodeZoom 吗？
const zoomApi = await Eval(`(async () => {
  const m = await import('/js/ui/codeview.js');
  return Object.keys(m).filter((k) => /zoom/i.test(k));
})()`);
console.log("zoom API:", JSON.stringify(zoomApi));

await new Promise((r) => setTimeout(r, 600));
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
    report.push({ n, colWs, guides, textHead: text.slice(0, 20), mkLen: mk.textContent.length });
  }
  return { report, zoom: document.getElementById('code-viewer').style.getPropertyValue('--code-zoom'), breadcrumb: document.getElementById('code-breadcrumb')?.innerText };
})()`);
console.log("breadcrumb:", out.breadcrumb, "zoom:", out.zoom);
for (const r of out.report) console.log(`L${r.n} col=${r.colWs} guides=${JSON.stringify(r.guides)} mkLen=${r.mkLen} | ${r.textHead}`);
const shot = await cdp("Page.captureScreenshot", { format: "png" });
const fs = await import("node:fs");
const p = "C:/Users/luoji/Desktop/firstep/.scratch/code-page-vscode-overhaul/shot-real-open.png";
fs.writeFileSync(p, Buffer.from(shot.result.data, "base64"));
console.log("截图:", p);
process.exit(0);
