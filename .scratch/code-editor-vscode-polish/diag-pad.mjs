// 调试（code-editor-vscode-polish/02）：右留白 / gutter 计数
const targets = await (await fetch("http://127.0.0.1:9251/json/list")).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
console.log(await Eval(`(() => {
  const hl = document.querySelector('#code-viewer .code-hl');
  const ta = document.querySelector('#code-viewer .code-ta');
  return JSON.stringify({
    hl: hl ? getComputedStyle(hl).padding : '?',
    ta: ta ? getComputedStyle(ta).padding : '?',
    hlr: hl ? getComputedStyle(hl).paddingRight : '?',
    tar: ta ? getComputedStyle(ta).paddingRight : '?',
    eq1: !!hl && !!ta && getComputedStyle(hl).paddingRight === '24px',
    eq2: !!hl && !!ta && getComputedStyle(ta).paddingRight === '24px',
    gut: document.querySelectorAll('#code-viewer .code-gutter-line').length,
    empty: !!document.querySelector('#code-viewer .code-empty'),
  });
})()`));
process.exit(0);
