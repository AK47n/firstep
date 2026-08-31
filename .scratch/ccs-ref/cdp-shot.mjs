// CDP 截图/取样式小工具：新开 target 到指定 URL，等待表达式，截图 + 提取 CSS 变量。
// 用法：node .scratch/ccs-ref/cdp-shot.mjs <url> <waitExpr> <outPng> [varsJsonExpr]
import { writeFileSync } from "node:fs";

const [url, waitExpr, outPng, varsExpr] = process.argv.slice(2);
const CDP = 9251;

const t = await (
  await fetch(`http://127.0.0.1:${CDP}/json/new?${encodeURIComponent(url)}`, { method: "PUT" })
).json();

const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};

// 等加载
let ok = false;
for (let i = 0; i < 120; i++) {
  try { ok = await Eval(waitExpr); } catch {}
  if (ok) break;
  await new Promise((r) => setTimeout(r, 500));
}
console.log("wait: " + (ok ? "OK" : "TIMEOUT"));

if (varsExpr) {
  const vars = await Eval(varsExpr);
  console.log("VARS: " + JSON.stringify(vars, null, 1));
}

const shot = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
writeFileSync(outPng, Buffer.from(shot.result.data, "base64"));
console.log("shot -> " + outPng);
process.exit(0);
