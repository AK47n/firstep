// 诊断：askSelection 链路（smoke-05 失败项）
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
console.log("选区状态:", await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  return ta ? { selStart: ta.selectionStart, selEnd: ta.selectionEnd, len: ta.value.length } : 'no ta';
})()`));
console.log("按钮:", await Eval(`(() => {
  const b = document.querySelector('.code-ai-selection-btn');
  return b ? { hidden: b.classList.contains('hidden'), left: b.style.left, top: b.style.top } : 'no btn';
})()`));
console.log("点击后 input.value:", await Eval(`(() => {
  const b = document.querySelector('.code-ai-selection-btn');
  if (b) { b.click(); }
  return document.getElementById('code-ai-chat-input').value;
})()`));
console.log("再查选区:", await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  return ta ? { selStart: ta.selectionStart, selEnd: ta.selectionEnd } : 'no ta';
})()`));
ws.close();
