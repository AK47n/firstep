// 截图：修复后「生成」栏底部（reload 拿新 CSS → 激活生成 → 滚到底 → 截图）。
const CDP = 9251;
const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
if (!page) { console.error("no page"); process.exit(1); }
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
await Eval(`document.querySelector('nav button[data-tab="generate"]')?.click()`);
await new Promise((r) => setTimeout(r, 400));
console.log("tab-code display =", await Eval(`getComputedStyle(document.getElementById('tab-code')).display`));
console.log("scrollHeight =", await Eval(`document.body.scrollHeight`));
await Eval(`window.scrollTo(0, document.body.scrollHeight)`);
await new Promise((r) => setTimeout(r, 700));
console.log("scrollY =", await Eval(`window.scrollY`));
const shot = await cdp("Page.captureScreenshot", { format: "png" });
if (!shot.result || !shot.result.data) { console.error("screenshot failed:", JSON.stringify(shot).slice(0, 300)); process.exit(1); }
const { writeFileSync } = await import("node:fs");
writeFileSync(".scratch/code-viewer-editor/diag-generate-bottom.png", Buffer.from(shot.result.data, "base64"));
console.log("shot saved");
process.exit(0);
