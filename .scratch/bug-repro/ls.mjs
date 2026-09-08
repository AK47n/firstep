// 探针：localStorage 持久化 + .code-ai-chat-panel/.code-statusbar button 样式 + HTML textarea class 核对
const t = (await (await fetch("http://127.0.0.1:9231/json/list")).json()).find((x) => x.type === "page" && x.url.includes("8000"));
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((r) => { ws.onopen = r; });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
await cdp("Runtime.enable");
const out = await cdp("Runtime.evaluate", { expression: `
(() => {
  const ls = {};
  for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); ls[k] = localStorage.getItem(k); }
  const sb = document.querySelector(".code-statusbar");
  const btn = document.querySelector("#btn-code-compile");
  const ta = document.querySelector("#code-ai-chat-input");
  const cs = getComputedStyle(btn);
  const tacs = getComputedStyle(ta);
  const layout = document.querySelector(".code-layout");
  return {
    localStorage: ls,
    statusbarVars: { treeW: getComputedStyle(layout).getPropertyValue("--code-tree-w"), sideW: getComputedStyle(layout).getPropertyValue("--code-side-w") },
    compileBtn: { cs: { width: cs.width, height: cs.height, padding: cs.padding, fontSize: cs.fontSize, lineHeight: cs.lineHeight, whiteSpace: cs.whiteSpace, flex: cs.flex, letterSpacing: cs.letterSpacing }, text: btn.innerText },
    saveAllBtn: { w: document.querySelector("#btn-code-save-all").getBoundingClientRect().width, h: document.querySelector("#btn-code-save-all").getBoundingClientRect().height },
    taClass: ta.className, taCS: { width: tacs.width, height: tacs.height, padding: tacs.padding, fontSize: tacs.fontSize, flex: tacs.flex, minHeight: tacs.minHeight },
  };
})()
`, returnByValue: true });
console.log(JSON.stringify(out.result.result.value, null, 2));
ws.close();
