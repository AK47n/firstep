// 调试 fold smoke 状态
const targets = await (await fetch("http://127.0.0.1:9251/json/list")).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
console.log(await Eval(`(() => {
  const g = [...document.querySelectorAll('#code-viewer .code-gutter-line')].map((x) => x.dataset.codeLine);
  const ta = document.querySelector('#code-viewer .code-ta');
  return JSON.stringify({
    gutter: g,
    gcls: [...document.querySelectorAll('#code-viewer .code-gutter-line')].map((x) => x.className),
    ph: !!document.querySelector('#code-viewer .code-gutter-ph'),
    val: ta ? ta.value : null,
    hasPhText: ta ? ta.value.includes('… 2 行') : false,
  });
})()`));
process.exit(0);
