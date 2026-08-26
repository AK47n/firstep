// 诊断：页面 reload 后 JS 可用性
const CDP = 9251;
let targets = null;
for (let i = 0; i < 30 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000")) || targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const ev = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result && r.result.exceptionDetails) return "EXC: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)).slice(0, 200);
  const v = r.result && r.result.result && r.result.result.value;
  return v === undefined ? "(undefined)" : v;
};
console.log("before reload:", await ev("document.readyState"));
await cdp("Page.reload", { ignoreCache: true });
await new Promise((r) => setTimeout(r, 4000));
console.log("readyState:", await ev("document.readyState"));
console.log("topicGrid el:", await ev("!!document.getElementById('topic-grid')"));
console.log("cards:", await ev("document.querySelectorAll('#topic-grid .topic-card').length"));
console.log("loadTopics:", await ev("typeof window.loadTopics"));
console.log("loadTopicPdf:", await ev("typeof window.loadTopicPdf"));
console.log("state:", await ev("typeof window.state"));
console.log("topic tab visible:", await ev("(() => { const t = document.querySelector('#tab-topic'); return t ? !t.classList.contains('hidden') : 'no-el'; })()"));
console.log("topic-msg:", await ev("(document.getElementById('topic-msg')||{}).textContent||'none'"));
ws.close(); process.exit(0);
