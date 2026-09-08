// 诊断 4：代码栏顶部黑线来源——列出顶部节点几何/背景/边框。
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

await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('code-viewer')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }
await Eval(`document.querySelector('nav button[data-tab="code"]')?.click()`);
await new Promise((r) => setTimeout(r, 500));

const info = await Eval(`(() => {
  const probe = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return { sel, missing: true };
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return {
      sel,
      y: Math.round(r.y), h: Math.round(r.height), w: Math.round(r.width),
      bg: cs.backgroundColor,
      borderTop: cs.borderTopWidth + ' ' + cs.borderTopColor,
      borderBottom: cs.borderBottomWidth + ' ' + cs.borderBottomColor,
    };
  };
  return [
    probe('.code-layout'),
    probe('.code-pane-tree .code-pane-title'),
    probe('.code-pane-action'),
    probe('.code-pane-main'),
    probe('#code-tabs'),
    probe('.code-file-path'),
    probe('#code-viewer'),
    probe('.code-statusbar'),
  ];
})()`);
console.log(JSON.stringify(info, null, 1));

// 页面顶部 0..200px 内所有「有高度且有背景或边框」的块级元素（按 y 排序）
const bands = await Eval(`(() => {
  const out = [];
  const all = document.querySelectorAll('main .code-layout, main .code-layout *');
  for (const el of all) {
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    if (r.height < 1 || r.height > 600) continue;
    if (r.top < 40 || r.top > 200) continue;
    if (cs.display === 'none') continue;
    const hasColor = cs.backgroundColor !== 'rgba(0, 0, 0, 0)' || cs.borderTopWidth !== '0px' || cs.borderBottomWidth !== '0px';
    if (!hasColor) continue;
    out.push({
      tag: el.tagName + '.' + String(el.className).slice(0, 40),
      top: Math.round(r.top), h: Math.round(r.height),
      bg: cs.backgroundColor, bt: cs.borderTopWidth, bb: cs.borderBottomWidth,
    });
  }
  return out.sort((a, b) => a.top - b.top);
})()`);
console.log(JSON.stringify(bands, null, 1));
process.exit(0);
