// 诊断 7b：深滚动位置切 PDF——验证 scrollTo 回顶（无钳位跳变）
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
await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try { ready = await Eval(`document.readyState === 'complete' && !!document.getElementById('tab-pdf')`); } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
// 生成页滚到底部
await Eval(`document.querySelector('nav button[data-tab="generate"]')?.click()`);
await new Promise((r) => setTimeout(r, 500));
await Eval(`window.scrollTo(0, document.documentElement.scrollHeight)`);
await new Promise((r) => setTimeout(r, 200));
console.log("生成页滚底:", JSON.stringify(await Eval(`({ scrollY: window.scrollY, max: document.documentElement.scrollHeight - innerHeight })`)));
// 切 PDF（先等生成页图片/内容就绪,让 PDF 走 loading→完成）
await Eval(`document.querySelector('nav button[data-tab="pdf"]')?.click()`);
await new Promise((r) => setTimeout(r, 50));
console.log("切 pdf 立即:", JSON.stringify(await Eval(`({ scrollY: window.scrollY, scrollH: document.documentElement.scrollHeight })`)));
await new Promise((r) => setTimeout(r, 1500));
console.log("pdf 完成:", JSON.stringify(await Eval(`({ scrollY: window.scrollY, scrollH: document.documentElement.scrollHeight })`)));
process.exit(0);
