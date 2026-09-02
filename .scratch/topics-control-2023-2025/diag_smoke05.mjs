// 诊断：页面加载状态与全局。
const CDP = 9251;
let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
const page = targets.find((t) => t.type === "page" && t.url.includes("127.0.0.1:8000"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => (await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result?.result?.value;

console.log("url:", page.url);
console.log("readyState:", await Eval(`document.readyState`));
console.log("tab-topic:", await Eval(`!!document.getElementById('tab-topic')`));
console.log("state:", await Eval(`typeof state`));
console.log("nav buttons:", await Eval(`[...document.querySelectorAll('nav button')].map(b=>b.textContent.trim()).join('|')`));
console.log("body 前 200:", await Eval(`document.body.textContent.slice(0, 200)`));
console.log("加载错误（performance entries）:", await Eval(`performance.getEntriesByType('resource').filter(e=>e.initiatorType==='script').slice(0,8).map(e=>e.name.split('/').slice(-2).join('/')+':'+(e.duration?Math.round(e.duration)+'ms':'?')).join(' | ')`));
ws.close();
