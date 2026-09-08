// 诊断 6：切到 PDF 栏时滚动条/布局宽度变化（用户反馈「微微变大然后左栏被往左挤、微闪」）。
const CDP = 9251;
const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval: " + (r.result.exceptionDetails.exception?.description || "?"));
  return r.result?.result?.value;
};

await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('tab-pdf')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }
await Eval(`document.querySelector('nav button[data-tab="generate"]')?.click()`);
await new Promise((r) => setTimeout(r, 300));

const before = await Eval(`(() => ({
  innerW: window.innerWidth,
  docClientW: document.documentElement.clientWidth,
  scrollH: document.documentElement.scrollHeight,
  clientH: document.documentElement.clientHeight,
  genW: document.getElementById('tab-generate').getBoundingClientRect().width,
}))()`);
console.log("before(generate):", JSON.stringify(before));

// 点 PDF → 立即测 → 等 loadPdfs 完成后测
await Eval(`document.querySelector('nav button[data-tab="pdf"]')?.click()`);
const immediate = await Eval(`(() => ({
  innerW: window.innerWidth,
  docClientW: document.documentElement.clientWidth,
  scrollH: document.documentElement.scrollHeight,
  clientH: document.documentElement.clientHeight,
  pdfW: document.getElementById('tab-pdf').getBoundingClientRect().width,
  pdfChildren: document.getElementById('tab-pdf').children.length,
}))()`);
console.log("immediate(after click):", JSON.stringify(immediate));
await new Promise((r) => setTimeout(r, 1500));
const settled = await Eval(`(() => ({
  innerW: window.innerWidth,
  docClientW: document.documentElement.clientWidth,
  scrollH: document.documentElement.scrollHeight,
  clientH: document.documentElement.clientHeight,
  pdfW: document.getElementById('tab-pdf').getBoundingClientRect().width,
  pdfChildren: document.getElementById('tab-pdf').children.length,
}))()`);
console.log("settled(after load):", JSON.stringify(settled));
process.exit(0);
