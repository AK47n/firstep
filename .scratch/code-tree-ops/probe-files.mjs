// 探针2：页面内 fetch no-store 是否拿到修复内容 + 当前模块源码文本头部
const CDP = 9231;
const list = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = list.find((t) => t.type === "page" && t.url.includes("127.0.0.1:8000")) || list.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails));
  return r.result?.result?.value;
};
const t1 = await Eval("fetch('/js/ui/code-tree-ops.js',{cache:'no-store'}).then(r=>r.text()).then(t=>t.includes('dirtySavableTabCount,'))");
const t2 = await Eval("fetch('/js/ui/codeeditor.js',{cache:'no-store'}).then(r=>r.text()).then(t=>t.includes('if (e.shiftKey) return'))");
console.log("no-store tree-ops import:", t1, "| no-store codeeditor guard:", t2);
process.exit(0);
