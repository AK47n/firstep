// 验证修复：注入候选 CSS → 检查按钮 rect/文本是否单行
const t = (await (await fetch("http://127.0.0.1:9231/json/list")).json()).find((x) => x.type === "page" && x.url.includes("8000"));
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((r) => { ws.onopen = r; });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const ev = async (expression, awaitPromise = false) => {
  const r = await cdp("Runtime.evaluate", { expression, awaitPromise, returnByValue: true });
  if (r.result.exceptionDetails) { console.log("EXC:", JSON.stringify(r.result.exceptionDetails)); return null; }
  return r.result.result.value;
};
await cdp("Runtime.enable");

const before = await ev(`(() => {
  const b = document.querySelector("#btn-code-compile"); const r = b.getBoundingClientRect();
  return { w: Math.round(r.width), h: Math.round(r.height) };
})()`);
console.log("before:", JSON.stringify(before));

await ev(`(() => {
  const st = document.createElement("style");
  st.textContent = ".code-statusbar button { flex: none !important; white-space: nowrap !important; }";
  document.head.appendChild(st);
  return 1;
})()`);
await wait(300);

const after = await ev(`(() => {
  const info = (id) => { const el = document.getElementById(id); if (!el) return null; const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return { w: Math.round(r.width), h: Math.round(r.height), text: el.innerText, whiteSpace: cs.whiteSpace, flex: cs.flex }; };
  const sb = document.querySelector(".code-statusbar");
  const sbRect = sb.getBoundingClientRect();
  return { sbH: Math.round(sbRect.height), saveAll: info("btn-code-save-all"), compile: info("btn-code-compile"), label: info("code-dir-label") };
})()`);
console.log("after:", JSON.stringify(after, null, 2));
ws.close();
