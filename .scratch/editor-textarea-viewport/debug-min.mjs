// 极简：连接 + 1+1
const t = await (await fetch("http://127.0.0.1:9251/json/list")).json();
const page = t.find((x) => x.type === "page" && x.url.startsWith("http://127.0.0.1:8000/"));
console.log("page", page.url);
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
console.log("ws open");
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const r = await Promise.race([
  cdp("Runtime.evaluate", { expression: "1+1", returnByValue: true }),
  new Promise((_, rej) => setTimeout(() => rej(new Error("eval timeout")), 5000)),
]);
console.log("eval:", JSON.stringify(r.result));
process.exit(0);
