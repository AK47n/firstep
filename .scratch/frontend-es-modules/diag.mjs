// 诊断：页面 module 为何未执行（frontend-es-modules/02 后冒烟异常）
const CDP = 9251;
const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
if (!page) { console.error("no page"); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0;
const pending = new Map();
const events = [];
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === "Runtime.exceptionThrown") {
    const d = m.params.exceptionDetails;
    events.push("EXC@L" + d.lineNumber + "C" + d.columnNumber + ": " + (d.exception?.description || d.text).slice(0, 200));
  }
  if (m.method === "Log.entryAdded" && m.params.entry.level === "error") {
    events.push("LOG: " + m.params.entry.text.slice(0, 250));
  }
  if (m.method === "Network.loadingFailed") {
    events.push("NETFAIL: " + m.params.errorText + " " + (m.params.blockedReason || ""));
  }
  if (m.method === "Network.responseReceived" && m.params.response.status >= 400) {
    events.push("HTTP" + m.params.response.status + ": " + m.params.response.url);
  }
};
const cdp = (method, params = {}) => new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  return r.result?.result?.value ?? (r.result?.exceptionDetails ? "EXCEPTION: " + JSON.stringify(r.result.exceptionDetails.exception?.description).slice(0, 250) : undefined);
};
await cdp("Runtime.enable");
await cdp("Log.enable");
await cdp("Network.enable");
await cdp("Page.reload", { ignoreCache: true });
await new Promise((r) => setTimeout(r, 3500));
console.log("=== events ===");
events.slice(0, 15).forEach((e) => console.log(e));
console.log("=== probes ===");
console.log("esc type:", await Eval(`typeof window.esc`));
console.log("readyState:", await Eval(`document.readyState`));
console.log("module scripts:", await Eval(`document.querySelectorAll('script[type=module]').length`));
console.log("pdf fn probe:", await Eval(`typeof window.pdfSubdir`));
console.log("tab-master exists:", await Eval(`!!document.getElementById('tab-master')`));
process.exit(0);
