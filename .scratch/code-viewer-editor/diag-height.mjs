// 诊断 5：代码栏高度链——header 实际高度 vs var(--header-h)、body 可滚性。
const CDP = 9251;
const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval: " + (r.result.exceptionDetails.exception?.description || "?"));
  return r.result?.result?.value;
};

// 先 reload 拿最新 DOM（index.html 修改后页面内存还是旧结构）
await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('tab-code')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }
await Eval(`document.querySelector('nav button[data-tab="code"]')?.click()`);
await new Promise((r) => setTimeout(r, 400));

const info = await Eval(`(() => {
  const rootCS = getComputedStyle(document.documentElement);
  const header = document.querySelector('header');
  const hr = header ? header.getBoundingClientRect() : null;
  const code = document.getElementById('tab-code');
  const cr = code.getBoundingClientRect();
  const sc = document.scrollingElement;
  return {
    innerH: window.innerHeight,
    headerVar: rootCS.getPropertyValue('--header-h').trim(),
    headerActual: hr ? Math.round(hr.height) : null,
    headerBottom: hr ? Math.round(hr.bottom) : null,
    tabCodeTop: Math.round(cr.top),
    tabCodeHeight: Math.round(cr.height),
    tabCodeBottom: Math.round(cr.bottom),
    scrollerScrollH: sc.scrollHeight,
    scrollerClientH: sc.clientHeight,
    bodyScrollH: document.body.scrollHeight,
    bodyH: document.body.getBoundingClientRect().height,
    scrollY: window.scrollY,
    activeTab: document.querySelector('nav button[data-tab].active')?.dataset.tab || null,
    domOrder: [...document.body.children].filter((c) => c.tagName !== 'SCRIPT' && c.tagName !== 'STYLE').map((c) => c.id || c.tagName + '.' + String(c.className).slice(0, 12)).slice(0, 6),
  };
})()`);
console.log(JSON.stringify(info, null, 1));
process.exit(0);
