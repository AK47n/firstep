// probe-css-viewport.mjs：在 CSS 884x462（模拟 Windows 125% 缩放）下复现真实工程
import { writeFileSync } from "node:fs";
const t = (await (await fetch("http://127.0.0.1:9231/json/list")).json()).find((x) => x.type === "page" && x.url.includes("8000"));
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((r) => { ws.onopen = r; });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

await cdp("Runtime.enable");
await cdp("Page.enable");
await cdp("Emulation.setDeviceMetricsOverride", { width: 884, height: 462, deviceScaleFactor: 1.25, mobile: false });
await wait(400);

const ev = async (expression, awaitPromise = false) => {
  const r = await cdp("Runtime.evaluate", { expression, awaitPromise, returnByValue: true });
  if (r.result.exceptionDetails) { console.log("EXC:", JSON.stringify(r.result.exceptionDetails)); return null; }
  return r.result.result.value;
};

// 若页面尚在真实工程则复用，否则重新打开
const state = await ev(`(async () => {
  if (document.querySelector("#tab-code") && document.querySelector("#code-ai-chat-input")) return { already: true };
  const m = await import("/js/ui/codeview.js");
  if (typeof m.openCodeViewer !== "function") return { already: false, err: "no openCodeViewer" };
  await m.openCodeViewer("C:/Users/luoji/Desktop/2024H_Auto_Car_MSPM0");
  return { already: false };
})()`, true);
console.log("state:", JSON.stringify(state));
await wait(600);

const dump = await ev(`(() => {
  const q = (sel) => document.querySelector(sel);
  const info = (sel) => {
    const el = q(sel); if (!el) return null;
    const r = el.getBoundingClientRect();
    return { sel, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
  };
  const btn = (sel) => { const el = q(sel); if (!el) return null; const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), text: (el.textContent||"").trim(), whiteSpace: cs.whiteSpace, flex: cs.flex }; };
  return {
    vp: { w: innerWidth, h: innerHeight, dpr: devicePixelRatio },
    bodyScroll: { sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight, cw: document.documentElement.clientWidth, ch: document.documentElement.clientHeight },
    els: [info("#tab-code .card"), info(".code-layout"), info(".code-pane-tree"), info(".code-pane-main"), info(".code-pane-side"),
      info("#code-compile-panel"), info("#code-change-panel"), info("#code-ai-chat-panel"), info("#code-fix-panel"), info(".code-statusbar"),
      info("#code-viewer"), info(".code-tabs")],
    btns: [btn("#btn-code-ai-collapse"), btn("#btn-code-ai-send"), btn("#btn-code-compile"), btn("#btn-code-save-all")],
    statusbarText: q(".code-statusbar")?.innerText,
    aiPanelClass: q("#code-ai-chat-panel")?.className,
    headerH: q("header")?.getBoundingClientRect().height,
  };
})()`);
console.log(JSON.stringify(dump, null, 2));

const shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync("C:/Users/luoji/Desktop/firstep/.scratch/bug-repro/css-884.png", Buffer.from(shot.result.data, "base64"));
console.log("saved css-884.png");
ws.close();
