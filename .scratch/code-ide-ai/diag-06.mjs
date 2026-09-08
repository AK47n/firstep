// 诊断 smoke-06 S3 失败
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
console.log("toasts:", await Eval(`Array.from(document.querySelectorAll('#toast-root .toast')).map((t) => t.textContent)`));
console.log("overlay:", await Eval(`!!document.querySelector('.ref-files-overlay')`));
console.log("btn:", await Eval(`Array.from(document.querySelectorAll('[data-ai-preview]')).map((b) => b.dataset.aiPreview)`));
console.log("msgs:", await Eval(`(window.__stubReply || '')`));
console.log("对话区 ai:", await Eval(`document.querySelectorAll('#code-ai-chat-body .sugg-msg.ai').length`));
// 直接点按钮再查
console.log("click result:", await Eval(`(() => {
  const b = document.querySelector('#code-ai-chat-body [data-ai-preview]');
  if (!b) return 'no btn';
  b.click();
  return 'clicked';
})()`));
await new Promise((r) => setTimeout(r, 2500));
console.log("toasts2:", await Eval(`Array.from(document.querySelectorAll('#toast-root .toast')).map((t) => t.textContent)`));
console.log("overlay2:", await Eval(`!!document.querySelector('.ref-files-overlay')`));
ws.close();
