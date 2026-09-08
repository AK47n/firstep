// dump 对比 hl 层与 marks 层的 data-code-line 与行文本
const CDP = 9251;
const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
};
let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000/"));
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
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + JSON.stringify(r.result.exceptionDetails));
  return r.result?.result?.value;
};
const out = await Eval(`(() => {
  const hlRows = [...document.querySelectorAll('#code-viewer .code-hl-line')].slice(0, 12).map((el) => ({ n: el.dataset.codeLine, t: el.textContent.slice(0, 14) }));
  const mkRows = [...document.querySelectorAll('#code-viewer .code-marks-line')].slice(0, 12).map((el) => ({ n: el.dataset.codeLine, t: el.textContent.slice(0, 14) }));
  const win = document.getElementById('code-viewer');
  return { hlRows, mkRows, scrollTop: win.scrollTop, childHl: document.querySelector('#code-viewer .code-hl')?.childElementCount, childMk: document.querySelector('#code-viewer .code-marks')?.childElementCount };
})()`);
console.log(JSON.stringify(out, null, 2));
process.exit(0);
