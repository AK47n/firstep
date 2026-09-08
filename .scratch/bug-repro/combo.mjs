// 组合探针：A) 侧栏收起态 B) 打开 readme.md C) 横向溢出检查 —— 每步截图
import { writeFileSync } from "node:fs";
const t = (await (await fetch("http://127.0.0.1:9231/json/list")).json()).find((x) => x.type === "page" && x.url.includes("8000"));
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((r) => { ws.onopen = r; });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const ev = async (expression, awaitPromise = false) => {
  const r = await cdp("Runtime.evaluate", { expression, awaitPromise, returnByValue: true });
  if (r.result.exceptionDetails) { console.log("EXC:", JSON.stringify(r.result.exceptionDetails)); return null; }
  return r.result.result.value;
};
const shot = async (name) => {
  const s = await cdp("Page.captureScreenshot", { format: "png" });
  writeFileSync("C:/Users/luoji/Desktop/firstep/.scratch/bug-repro/" + name, Buffer.from(s.result.data, "base64"));
  console.log("saved", name);
};
await cdp("Runtime.enable");
await cdp("Page.enable");

// A) 侧栏收起
await ev(`(() => { document.querySelector(".code-layout").classList.add("side-collapsed"); return 1; })()`);
await wait(300);
await shot("A-side-collapsed.png");

// A2) 布局关键值
const a2 = await ev(`(() => {
  const q = (s) => document.querySelector(s);
  const info = (s) => { const el = q(s); if (!el) return null; const r = el.getBoundingClientRect(); return { s, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }; };
  return {
    overflowX: document.documentElement.scrollWidth + " vs innerWidth=" + innerWidth,
    gridCols: getComputedStyle(q(".code-layout")).gridTemplateColumns,
    layout: [info(".code-layout"), info(".code-pane-main"), info(".code-pane-side"), info(".code-side-rail"), info("#code-ai-chat-panel"), info(".code-statusbar")],
  };
})()`);
console.log("A2:", JSON.stringify(a2, null, 2));

// B) 打开 readme.md（md 预览态）
await ev(`(() => { const items = [...document.querySelectorAll("[data-code-file]")]; const it = items.find((b) => (b.dataset.codeFile || "").toLowerCase().endsWith("readme.md")); if (it) it.click(); return it ? it.dataset.codeFile : "none"; })()`);
await wait(800);
await shot("B-md-open.png");
const b2 = await ev(`(() => {
  const q = (s) => document.querySelector(s);
  const info = (s) => { const el = q(s); if (!el) return null; const r = el.getBoundingClientRect(); return { s, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }; };
  return {
    layout: [info("#code-viewer"), info(".code-pane-main"), info("#code-ai-chat-panel"), info(".code-statusbar")],
    viewerHTML: (q("#code-viewer")?.innerHTML || "").slice(0, 400),
    pathBar: q(".code-file-path")?.innerText,
  };
})()`);
console.log("B2:", JSON.stringify(b2, null, 2));
ws.close();
