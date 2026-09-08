// 调试（code-editor-vscode-polish/01）：状态栏 Ln/Col 刷新路径
const CDP = 9251;
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

console.log("info1:", await Eval(`document.getElementById('code-statusbar-info').textContent`));
console.log("has ta:", await Eval(`!!document.querySelector('#code-viewer .code-ta')`));
console.log("step:", await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  const lines = ta.value.split('\\n');
  const pos = lines.slice(0, 2).join('\\n').length + 4;
  ta.setSelectionRange(pos, pos);
  ta.dispatchEvent(new Event('keyup', { bubbles: true }));
  return JSON.stringify({ pos, sel: ta.selectionStart, line3: lines[2] });
})()`));
await new Promise((r) => setTimeout(r, 300));
console.log("info2:", await Eval(`document.getElementById('code-statusbar-info').textContent`));
console.log("active line:", await Eval(`(document.querySelector('#code-viewer .code-hl-line.active') || {}).dataset ? document.querySelector('#code-viewer .code-hl-line.active').dataset.codeLine : 'none'`));
process.exit(0);
