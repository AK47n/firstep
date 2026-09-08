// 截图：最终版代码栏（1440 全屏 + 顶部 150px），验证无空隙无黑线无滚动。
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

await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('tab-code')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }
await Eval(`document.querySelector('nav button[data-tab="code"]')?.click()`);
await new Promise((r) => setTimeout(r, 500));

const top = await cdp("Page.captureScreenshot", { format: "png", clip: { x: 0, y: 0, width: 1440, height: 150, scale: 1 } });
writeFileSync(".scratch/code-viewer-editor/diag-top-final.png", Buffer.from(top.result.data, "base64"));
const full = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(".scratch/code-viewer-editor/shot-code-final.png", Buffer.from(full.result.data, "base64"));
console.log("shots saved");
console.log("scrollable =", await Eval(`document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight`));
process.exit(0);
