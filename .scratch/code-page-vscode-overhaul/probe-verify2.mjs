// 修复后高清截图（clip 正确格式）
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
const rects = await Eval(`(() => {
  const box = document.getElementById('code-viewer').getBoundingClientRect();
  const a = document.querySelector('#code-viewer .code-hl-line[data-code-line="43"]');
  const b = document.querySelector('#code-viewer .code-hl-line[data-code-line="60"]');
  if (!a || !b) return null;
  const ra = a.getBoundingClientRect();
  const rb = b.getBoundingClientRect();
  return { x: Math.max(0, Math.floor(ra.left - 30)), y: Math.max(0, Math.floor(ra.top - 14)),
    width: Math.ceil(rb.right - ra.left) + 100, height: Math.ceil(rb.bottom - ra.top) + 28, scale: 2.5 };
})()`);
console.log("clip:", JSON.stringify(rects));
const shot = await cdp("Page.captureScreenshot", { format: "png", clip: rects });
const fs = await import("node:fs");
const p = "C:/Users/luoji/Desktop/firstep/.scratch/code-page-vscode-overhaul/shot-fixed-guides.png";
fs.writeFileSync(p, Buffer.from(shot.result.data, "base64"));
console.log("高清截图:", p);
process.exit(0);
