// 探针：连 CDP，dump 当前页面状态（URL / 活动 tab / #tab-code 布局/代码栏关键元素）
const t = (await (await fetch("http://127.0.0.1:9231/json/list")).json()).find((x) => x.type === "page" && x.url.includes("8000"));
if (!t) { console.log("NO PAGE"); process.exit(1); }
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((r) => { ws.onopen = r; });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
await cdp("Runtime.enable");
const out = await cdp("Runtime.evaluate", { expression: `
(() => {
  const q = (sel) => document.querySelector(sel);
  const info = (sel) => {
    const el = q(sel); if (!el) return null;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return { sel, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
      display: cs.display, position: cs.position, flexDirection: cs.flexDirection, flex: cs.flex,
      gridTemplateColumns: cs.gridTemplateColumns, overflow: cs.overflow };
  };
  const active = document.querySelector("section.page.active");
  return {
    url: location.href,
    activeTab: active ? active.id : null,
    navButtons: [...document.querySelectorAll("header button, nav button")].map(b => b.textContent.trim()).filter(Boolean).slice(0, 30),
    layout: [
      info("#tab-code"), info("#tab-code .card"), info(".code-layout"),
      info(".code-pane-tree"), info(".code-pane-main"), info(".code-pane-side"),
      info("#code-compile-panel"), info("#code-change-panel"), info("#code-ai-chat-panel"), info("#code-fix-panel"),
      info(".code-statusbar"), info("#code-viewer"), info("#code-tabs"), info(".code-file-path"),
      info("#btn-code-ai-collapse"), info("#btn-code-ai-send"),
    ],
    aiPanelClass: q("#code-ai-chat-panel") ? q("#code-ai-chat-panel").className : null,
    aiPanelChildren: q("#code-ai-chat-panel") ? [...q("#code-ai-chat-panel").children].map(c => c.id || c.className) : null,
  };
})()
`, returnByValue: true });
console.log(JSON.stringify(out.result.result.value, null, 2));
ws.close();
