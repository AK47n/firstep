// 截图：2033 宽视口下代码栏顶部（复现用户截图的黑线）。
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

await cdp("Emulation.setDeviceMetricsOverride", { width: 2033, height: 900, deviceScaleFactor: 1, mobile: false });
await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('code-viewer')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }
await Eval(`document.querySelector('nav button[data-tab="code"]')?.click()`);
await new Promise((r) => setTimeout(r, 500));

const info = await Eval(`(() => {
  const probe = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return { sel, missing: true };
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return { sel, y: Math.round(r.y), h: Math.round(r.height),
      bg: cs.backgroundColor, bBottom: cs.borderBottomWidth + ' ' + cs.borderBottomColor };
  };
  return {
    innerWidth: window.innerWidth,
    title: probe('.code-pane-tree .code-pane-title'),
    tabs: probe('#code-tabs'),
    viewer: probe('#code-viewer'),
    pathBar: probe('.code-file-path'),
    layout: probe('.code-layout'),
  };
})()`);
console.log(JSON.stringify(info, null, 1));

const shot = await cdp("Page.captureScreenshot", {
  format: "png",
  clip: { x: 0, y: 0, width: 2033, height: 150, scale: 1 },
});
const { writeFileSync } = await import("node:fs");
writeFileSync(".scratch/code-viewer-editor/diag-top-2033.png", Buffer.from(shot.result.data, "base64"));
console.log("shot saved");
process.exit(0);
