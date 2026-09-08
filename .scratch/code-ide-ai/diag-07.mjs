// 诊断：顶层模块是否加载（按钮监听/桩计数）
const t = (await (await fetch("http://127.0.0.1:9231/json/list")).json()).find((x) => x.type === "page");
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((r) => { ws.onopen = r; });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const ev = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return "EXC: " + r.result.exceptionDetails.exception?.description;
  return r.result?.result?.value;
};
console.log("compileCount =", await ev("window.__compileCount"));
console.log("btn click listeners =", await ev("getEventListeners(document.getElementById('btn-code-compile')).click?.length ?? 0"));
console.log("fix-here click listeners =", await ev("getEventListeners(document.getElementById('btn-code-compile-fix-here')).click?.length ?? 0"));
console.log("code-dir label =", await ev("document.getElementById('code-dir-label').textContent"));
console.log("compile panel hidden =", await ev("document.getElementById('code-compile-panel').classList.contains('hidden')"));
console.log("compile status =", await ev("document.getElementById('code-compile-status').textContent"));
console.log("compile errors html len =", await ev("document.getElementById('code-compile-errors').innerHTML.length"));
ws.close();
