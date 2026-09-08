// 截图探针 v3：点 settings → 等 tab-settings active → 截图（不 scrollIntoView，
// 直接查看当前可视区域；设置页内容较长，先点检查再滚动卡片到视口内）。
import { writeFileSync } from "node:fs";

const CDP = 9252;

async function waitFor(fn, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try { if (await fn()) return true; } catch {}
    await new Promise((r) => setTimeout(r, 300));
  }
  return false;
}

let targets = null;
for (let i = 0; i < 60 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });

let seq = 0;
const pending = new Map();
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};

await cdp("Page.enable");
await cdp("Runtime.enable");

// 直接切 settings（页面已导航过，无需再 navigate）
await cdp("Runtime.evaluate", { expression: "document.querySelector('[data-tab=\"settings\"]').click()" });
await waitFor(async () => {
  const r = await cdp("Runtime.evaluate", {
    expression: "document.querySelector('[data-tab=\"settings\"]')?.getAttribute('aria-selected') === 'true' && !!document.querySelector('#tab-settings #btn-materials-check')",
    returnByValue: true,
  });
  return r.result?.result?.value === true;
});
console.log("settings tab active");

// 定位资料库卡到视口
await cdp("Runtime.evaluate", { expression: `
  const el = document.querySelector('#materials-update-results');
  if (el) el.scrollIntoView({ block: 'center' });
` });
await new Promise((r) => setTimeout(r, 400));
const shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(".scratch/materials-update/mats-settings.png", Buffer.from(shot.result.data, "base64"));
console.log("saved mats-settings.png");
process.exit(0);
