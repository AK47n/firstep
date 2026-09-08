// 复现探针：窄视口 565x474 → 打开 sample-proj 目录 → 打开 main.c → dump 布局 + 截图
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
await cdp("Emulation.setDeviceMetricsOverride", { width: 565, height: 474, deviceScaleFactor: 1, mobile: false });
await wait(300);

const ev = async (expression, awaitPromise = false) => {
  const r = await cdp("Runtime.evaluate", { expression, awaitPromise, returnByValue: true });
  if (r.result.exceptionDetails) { console.log("EXC:", JSON.stringify(r.result.exceptionDetails)); return null; }
  return r.result.result.value;
};

// 1) 打开目录
const openRes = await ev(`(async () => {
  const m = await import("/js/ui/codeview.js");
  if (typeof m.openCodeViewer !== "function") return "no openCodeViewer";
  await m.openCodeViewer("C:/Users/luoji/Desktop/firstep/.scratch/code-viewer/sample-proj");
  return "ok";
})()`, true);
console.log("openCodeViewer:", openRes);
await wait(800);

// 2) 打开 main.c（点树条目，事件委托路径最真实）
const openFile = await ev(`(() => {
  const items = [...document.querySelectorAll("[data-code-file]")];
  const item = items.find((b) => (b.dataset.codeFile || "").toLowerCase().endsWith("main.c"));
  if (!item) return "no main.c item; items=" + items.map((b) => b.dataset.codeFile).join(",");
  item.click();
  return "clicked " + item.dataset.codeFile;
})()`);
console.log("openFile:", openFile);
await wait(800);

// 3) 布局 dump
const dump = await ev(`(() => {
  const q = (sel) => document.querySelector(sel);
  const info = (sel) => {
    const el = q(sel); if (!el) return null;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return { sel, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
      display: cs.display, position: cs.position, flexDirection: cs.flexDirection, flex: cs.flex,
      gridTemplateColumns: cs.gridTemplateColumns, minWidth: cs.minWidth, width: cs.width };
  };
  const ai = q("#code-ai-chat-panel");
  const aiRect = ai ? ai.getBoundingClientRect() : null;
  return {
    vp: { w: innerWidth, h: innerHeight },
    layout: [
      info("#tab-code"), info("#tab-code .card"), info(".code-layout"),
      info(".code-pane-tree"), info(".code-pane-main"), info(".code-pane-side"),
      info("#code-compile-panel"), info("#code-change-panel"), info("#code-ai-chat-panel"), info("#code-fix-panel"),
      info(".code-statusbar"), info("#code-viewer"), info("#code-tabs"),
    ],
    aiPanelClass: ai ? ai.className : null,
    aiRect: aiRect ? { x: Math.round(aiRect.x), y: Math.round(aiRect.y), w: Math.round(aiRect.width), h: Math.round(aiRect.height) } : null,
    aiHeadText: ai ? ai.querySelector(".code-compile-head")?.innerText : null,
    aiHeadRect: ai ? (() => { const r = ai.querySelector(".code-compile-head")?.getBoundingClientRect(); return r ? { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) } : null; })() : null,
    inputRowRect: ai ? (() => { const r = ai.querySelector(".code-ai-chat-input-row")?.getBoundingClientRect(); return r ? { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) } : null; })() : null,
    statusbarText: q(".code-statusbar")?.innerText,
    treeHTML: (q("#code-tree")?.innerHTML || "").slice(0, 300),
    tabActive: document.querySelector("section.page.active")?.id,
  };
})()`);
console.log(JSON.stringify(dump, null, 2));

// 4) 截图
const shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync("C:/Users/luoji/Desktop/firstep/.scratch/bug-repro/repro-565.png", Buffer.from(shot.result.data, "base64"));
console.log("saved repro-565.png");
ws.close();
