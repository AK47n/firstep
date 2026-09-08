// materials-update 冒烟 v2：等页面完全初始化（tab 面板可见）再点检查。
// 依赖：8123 webapp + Chrome CDP 9252。
import { writeFileSync } from "node:fs";

const CDP = 9252;
const pageUrl = "http://127.0.0.1:8123/";

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
const jsErrors = [];
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") {
    jsErrors.push(msg.params.exceptionDetails?.exception?.description || "exception");
  }
};

await cdp("Page.enable");
await cdp("Runtime.enable");
await cdp("Page.navigate", { url: pageUrl });
// 等待设置 tab 点击可用（页面 init 完成：tab-settings 面板存在且有数据）
await waitFor(async () => {
  const r = await cdp("Runtime.evaluate", {
    expression: "document.querySelectorAll('[data-tab]').length > 0 && !document.querySelector('.global-loading')",
    returnByValue: true,
  });
  return r.result?.result?.value === true;
});
console.log("页面初始化完成");

await cdp("Runtime.evaluate", { expression: "document.querySelector('[data-tab=\"settings\"]').click()" });
await waitFor(async () => {
  const r = await cdp("Runtime.evaluate", {
    expression: "getComputedStyle(document.querySelector('#tab-settings')).display !== 'none' && !!document.querySelector('#tab-settings #btn-materials-check')",
    returnByValue: true,
  });
  return r.result?.result?.value === true;
});
console.log("设置页可见，btn-materials-check 存在");
await new Promise((r) => setTimeout(r, 500));

// 点检查
await cdp("Runtime.evaluate", { expression: "document.querySelector('#btn-materials-check').click()" });
await waitFor(async () => {
  const r = await cdp("Runtime.evaluate", {
    expression: "document.querySelector('#materials-update-results')?.textContent?.length > 3",
    returnByValue: true,
  });
  return r.result?.result?.value === true;
});
await new Promise((r) => setTimeout(r, 300));
const textResp = await cdp("Runtime.evaluate", {
  expression: "document.querySelector('#materials-update-results')?.textContent || ''",
  returnByValue: true,
});
console.log("检查结果文案:", textResp.result?.result?.value?.slice(0, 100));

// 滚动到资料库卡截图
await cdp("Runtime.evaluate", { expression: "document.querySelector('#materials-update-results').scrollIntoView({block:'center'})" });
await new Promise((r) => setTimeout(r, 300));
const shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(".scratch/materials-update/mats-check-result.png", Buffer.from(shot.result.data, "base64"));
console.log("截图保存");
console.log("JS 异常:", jsErrors.length ? jsErrors.slice(0, 3) : "无");
process.exit(jsErrors.length ? 1 : 0);
