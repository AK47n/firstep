// 诊断 7：PDF 栏切换闪动复现——从代码栏切 PDF，三个阶段（前/即刻/加载后）量
// 宽度与位移 + 截图。
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
const { writeFileSync } = await import("node:fs");
const snap = () => Eval(`(() => ({
  docW: document.documentElement.clientWidth,
  innerW: window.innerWidth,
  scrollH: document.documentElement.scrollHeight,
  clientH: document.documentElement.clientHeight,
  mainLeft: Math.round(document.querySelector('main').getBoundingClientRect().left),
  mainTop: Math.round(document.querySelector('main').getBoundingClientRect().top),
  mainW: Math.round(document.querySelector('main').getBoundingClientRect().width),
  marginTop: getComputedStyle(document.querySelector('main')).marginTop,
  scrollY: window.scrollY,
  pdfH: Math.round(document.getElementById('tab-pdf').getBoundingClientRect().height),
  rows: document.querySelectorAll('#pdf-rows tr').length,
}))()`);

await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
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

// 阶段 A：代码栏
await Eval(`document.querySelector('nav button[data-tab="code"]')?.click()`);
await new Promise((r) => setTimeout(r, 400));
console.log("A(code):", JSON.stringify(await snap()));
// 阶段 B：切 PDF 即刻（同步帧后）
await Eval(`document.querySelector('nav button[data-tab="pdf"]')?.click()`);
await new Promise((r) => setTimeout(r, 60));
console.log("B(pdf 即刻):", JSON.stringify(await snap()));
const sb = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(".scratch/code-viewer-editor/diag-pdf-immediate.png", Buffer.from(sb.result.data, "base64"));
// 阶段 C：加载完成
await new Promise((r) => setTimeout(r, 1800));
console.log("C(pdf 完成后):", JSON.stringify(await snap()));
const sc = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(".scratch/code-viewer-editor/diag-pdf-settled.png", Buffer.from(sc.result.data, "base64"));
console.log("shots saved");
process.exit(0);
