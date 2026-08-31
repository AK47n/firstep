// 附着 webapp 页面，取代码视图 .tok-fn / .tok-const 的实际计算颜色（工单 02 验证）。
// 用法：node .scratch/ccs-ref/eval-tok.mjs
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const fetchT = async (url, ms = 5000, method = "GET") => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { method, signal: ctl.signal }); } finally { clearTimeout(t); }
};
const targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
if (!page) { console.error("no page"); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || ""));
  return r.result?.result?.value;
};
const out = await Eval(`(() => {
  const pick = (sel) => {
    const el = document.querySelector(sel);
    return el ? getComputedStyle(el).color : null;
  };
  const fnEls = [...document.querySelectorAll('.code-view .tok-fn')].map((el) => el.textContent + '=' + getComputedStyle(el).color);
  const cnEls = [...document.querySelectorAll('.code-view .tok-const')].map((el) => el.textContent + '=' + getComputedStyle(el).color);
  return {
    theme: document.documentElement.getAttribute('data-theme') || 'dark',
    hasViewer: !!document.querySelector('.code-view'),
    fn: fnEls, const: cnEls,
    fnRule: pick('.tok-fn'), constRule: pick('.tok-const'),
  };
})()`);
console.log(JSON.stringify(out, null, 1));
process.exit(0);
