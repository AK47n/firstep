// verify2.mjs：修复后（grid-template-rows: minmax(0,1fr)）三视口综合回归
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
await cdp("Emulation.setDeviceMetricsOverride", { width: 1105, height: 578, deviceScaleFactor: 1, mobile: false });
await cdp("Page.reload", { ignoreCache: true });
await wait(1500);

const ev = async (expression, awaitPromise = false) => {
  const r = await cdp("Runtime.evaluate", { expression, awaitPromise, returnByValue: true });
  if (r.result.exceptionDetails) { console.log("EXC:", JSON.stringify(r.result.exceptionDetails)); return null; }
  return r.result.result.value;
};

// 重新打开真实工程 + beep.c（reload 后状态丢失）
await ev(`(async () => {
  const m = await import("/js/ui/codeview.js");
  await m.openCodeViewer("C:/Users/luoji/Desktop/2024H_Auto_Car_MSPM0");
  return "ok";
})()`, true);
await wait(700);
await ev(`(() => {
  const items = [...document.querySelectorAll("[data-code-file]")];
  const item = items.find((b) => (b.dataset.codeFile || "").toLowerCase().endsWith("beep.c"));
  if (item) item.click();
  return "done";
})()`);
await wait(700);

const dumpAt = async (w, h, dpr, name) => {
  await cdp("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: dpr, mobile: false });
  await wait(400);
  const d = await ev(`(() => {
    const q = (sel) => document.querySelector(sel);
    const info = (sel) => {
      const el = q(sel); if (!el) return null;
      const r = el.getBoundingClientRect();
      return { sel, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
    };
    const treeBox = q(".code-tree-box");
    const viewer = q("#code-viewer");
    return {
      vp: { w: innerWidth, h: innerHeight, dpr: devicePixelRatio },
      bodyScroll: { sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight },
      els: [info(".code-layout"), info(".code-pane-tree"), info(".code-pane-main"), info(".code-pane-side"),
        info("#code-ai-chat-panel"), info(".code-statusbar")],
      gridRows: getComputedStyle(q(".code-layout")).gridTemplateRows,
      treeScroll: treeBox ? { sh: treeBox.scrollHeight, ch: treeBox.clientHeight } : null,
      viewerScroll: viewer ? { sh: viewer.scrollHeight, ch: viewer.clientHeight } : null,
    };
  })()`);
  console.log("== " + name + " ==");
  console.log(JSON.stringify(d, null, 2));
  const shot = await cdp("Page.captureScreenshot", { format: "png" });
  writeFileSync("C:/Users/luoji/Desktop/firstep/.scratch/bug-repro/" + name + ".png", Buffer.from(shot.result.data, "base64"));
};

await dumpAt(884, 462, 1.25, "v2-884x462");
await dumpAt(1105, 578, 1, "v2-1105x578");
await dumpAt(565, 474, 1, "v2-565x474");
ws.close();
