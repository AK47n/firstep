// 诊断：reload 后捕获 console 错误（顶层模块加载失败定位）
const t = (await (await fetch("http://127.0.0.1:9231/json/list")).json()).find((x) => x.type === "page");
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((r) => { ws.onopen = r; });
let seq = 0; const pending = new Map();
const logs = [];
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  else if (m.method === "Runtime.exceptionThrown") {
    logs.push("EXC: " + (m.params.exceptionDetails.exception?.description || JSON.stringify(m.params.exceptionDetails)));
  } else if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") {
    logs.push("CONSOLE: " + m.params.args.map((a) => a.value ?? a.description ?? "").join(" "));
  } else if (m.method === "Log.entryAdded" && m.params.entry.level === "error") {
    logs.push("LOG: " + (m.params.entry.text || "") + " " + (m.params.entry.url || ""));
  }
};
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
await cdp("Runtime.enable");
await cdp("Log.enable");
await cdp("Page.enable");
await cdp("Network.enable");
await cdp("Network.setCacheDisabled", { cacheDisabled: true });
await cdp("Page.reload", { ignoreCache: true });
await new Promise((r) => setTimeout(r, 3000));
console.log(logs.join("\n") || "无错误");
ws.close();
