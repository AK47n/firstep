// 验证修复：刷新 → 打开目录+main.c → 滚动到底 → dump + 截图
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
await cdp("Runtime.enable");
await cdp("Page.enable");
await cdp("Emulation.setDeviceMetricsOverride", { width: 565, height: 474, deviceScaleFactor: 1, mobile: false });
await cdp("Page.reload", { ignoreCache: true });
await wait(2500);

await ev(`(async () => {
  const m = await import("/js/ui/codeview.js");
  await m.openCodeViewer("C:/Users/luoji/Desktop/firstep/.scratch/code-viewer/sample-proj");
  return 1;
})()`, true);
await wait(800);
const opened = await ev(`(() => {
  const items = [...document.querySelectorAll("[data-code-file]")];
  const it = items.find((b) => (b.dataset.codeFile || "").toLowerCase().endsWith("main.c"));
  if (it) it.click();
  return it ? "clicked" : "no item";
})()`);
await wait(800);
await ev(`(() => { scrollTo(0, document.documentElement.scrollHeight); return 1; })()`);
await wait(300);

const d = await ev(`(() => {
  const info = (id) => { const el = document.getElementById(id); if (!el) return null; const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return { w: Math.round(r.width), h: Math.round(r.height), text: (el.innerText || "").slice(0, 20), whiteSpace: cs.whiteSpace, flex: cs.flex }; };
  const sb = document.querySelector(".code-statusbar");
  const ta = document.getElementById("code-ai-chat-input");
  const tacs = getComputedStyle(ta);
  return {
    activeTab: document.querySelector("section.page.active")?.id,
    statusbarH: Math.round(sb.getBoundingClientRect().height),
    saveAll: info("btn-code-save-all"), compile: info("btn-code-compile"),
    label: info("code-dir-label"),
    ta: { cls: ta.className, w: Math.round(ta.getBoundingClientRect().width), h: Math.round(ta.getBoundingClientRect().height), fontSize: tacs.fontSize, flex: tacs.flex, minHeight: tacs.minHeight },
    collapse: info("btn-code-ai-collapse"), send: info("btn-code-ai-send"),
  };
})()`);
console.log(JSON.stringify(d, null, 2));
const s = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync("C:/Users/luoji/Desktop/firstep/.scratch/bug-repro/fixed-bottom.png", Buffer.from(s.result.data, "base64"));
console.log("saved fixed-bottom.png");
ws.close();
