// 完整回归：刷新后 565 视口 打开目录+main.c → 三列宽/状态栏/截图；再测侧栏收起 + 1440 宽视口
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
const cols = () => ev(`(() => {
  const q = (s) => document.querySelector(s);
  const info = (el) => { const r = el.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height) }; };
  return {
    grid: getComputedStyle(q(".code-layout")).gridTemplateColumns,
    tree: info(q(".code-pane-tree")), main: info(q(".code-pane-main")), side: info(q(".code-pane-side")),
    compile: info(document.getElementById("btn-code-compile")), saveAll: info(document.getElementById("btn-code-save-all")),
    sbH: Math.round(q(".code-statusbar").getBoundingClientRect().height),
    ai: info(document.getElementById("code-ai-chat-panel")),
  };
})()`);
await cdp("Runtime.enable");
await cdp("Page.enable");

// —— 565 视口（用户场景）——
await cdp("Emulation.setDeviceMetricsOverride", { width: 565, height: 474, deviceScaleFactor: 1, mobile: false });
await cdp("Page.reload", { ignoreCache: true });
await wait(2500);
await ev(`(async () => { const m = await import("/js/ui/codeview.js"); await m.openCodeViewer("C:/Users/luoji/Desktop/firstep/.scratch/code-viewer/sample-proj"); return 1; })()`, true);
await wait(800);
await ev(`(() => { const it = [...document.querySelectorAll("[data-code-file]")].find((b) => (b.dataset.codeFile || "").toLowerCase().endsWith("main.c")); if (it) it.click(); return 1; })()`);
await wait(800);
console.log("565 打开文件后:", JSON.stringify(await cols(), null, 1));
await ev(`(() => { scrollTo(0, document.documentElement.scrollHeight); return 1; })()`);
await wait(300);
let s = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync("C:/Users/luoji/Desktop/firstep/.scratch/bug-repro/final-565.png", Buffer.from(s.result.data, "base64"));
console.log("saved final-565.png");

// —— 侧栏收起态 565 ——
await ev(`(() => { document.querySelector(".code-layout").classList.add("side-collapsed"); return 1; })()`);
await wait(300);
console.log("565 侧栏收起:", JSON.stringify(await cols(), null, 1));
await ev(`(() => { document.querySelector(".code-layout").classList.remove("side-collapsed"); return 1; })()`);

// —— 1440 宽视口回归 ——
await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await wait(300);
console.log("1440 回归:", JSON.stringify(await cols(), null, 1));
ws.close();
