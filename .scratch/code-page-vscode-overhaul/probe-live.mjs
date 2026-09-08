// 抓当前页面实时状态：目录/标签/ta 内容/视口/几何
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
  const ta = document.querySelector('#code-viewer .code-ta');
  const tabs = [...document.querySelectorAll('#code-tabs .code-tab')].map((t) => t.textContent.trim());
  const treeRoots = [...document.querySelectorAll('#code-tree details')].slice(0, 20).map((d) => d.querySelector('summary')?.textContent.trim());
  const hlRows = [...document.querySelectorAll('#code-viewer .code-hl-line')];
  const first = hlRows[0], last = hlRows[hlRows.length - 1];
  const zoom = document.getElementById('code-viewer')?.style.getPropertyValue('--code-zoom');
  return {
    taLen: ta?.value?.length ?? -1,
    taFirst: ta?.value?.split('\\n')[0]?.slice(0, 40),
    taLine30: ta?.value?.split('\\n')[29]?.slice(0, 50),
    tabs, treeRoots,
    firstHL: first ? (first.dataset.codeLine + ':' + first.textContent.slice(0, 30)) : null,
    lastHL: last ? (last.dataset.codeLine + ':' + last.textContent.slice(0, 30)) : null,
    hlCount: hlRows.length,
    zoom,
    breadcrumb: document.getElementById('code-breadcrumb')?.innerText ?? null,
    statusbar: document.querySelector('#code-statusbar')?.innerText?.slice(0, 120) ?? null,
  };
})()`);
console.log(JSON.stringify(out, null, 2));
process.exit(0);
