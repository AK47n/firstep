// 诊断：S7 overlay 内容
const CDP = 9231;
let targets = null;
for (let i = 0; i < 20 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
const page = targets.find((t) => t.type === "page" && t.url.includes("127.0.0.1:8000")) || targets[0];
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return "ERR: " + (r.result.exceptionDetails.exception?.description || "?");
  return r.result?.result?.value;
};
console.log("overlay count:", await Eval(`document.querySelectorAll('.ref-files-overlay').length`));
console.log("overlay html head:", await Eval(`(document.querySelector('.ref-files-overlay') || {}).innerHTML ? document.querySelector('.ref-files-overlay').innerHTML.slice(0, 500) : 'none'`));
console.log("confirm-ok count:", await Eval(`document.querySelectorAll('.ref-files-overlay [data-confirm-ok]').length`));
console.log("buttons:", await Eval(`Array.from(document.querySelectorAll('[data-ai-preview]')).map((b) => b.dataset.aiPreview)`));
console.log("toasts:", await Eval(`Array.from(document.querySelectorAll('#toast-root .toast')).map((t) => t.textContent)`));
ws.close();
