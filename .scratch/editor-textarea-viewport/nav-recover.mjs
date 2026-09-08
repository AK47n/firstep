// 把 CDP 9251 的页面导航回 http://127.0.0.1:8000/（webapp 重启后 recovery）
const CDP = 9251;
const t = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = t.find((x) => x.type === "page");
if (!page) { console.error("no page"); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const r = await cdp("Page.navigate", { url: "http://127.0.0.1:8000/" });
console.log("navigate:", JSON.stringify(r.result));
await new Promise((res) => setTimeout(res, 2000));
const r2 = await cdp("Runtime.evaluate", { expression: "location.href", returnByValue: true });
console.log("url:", JSON.stringify(r2.result));
process.exit(0);
