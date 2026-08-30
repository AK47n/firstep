// 复核：设置页「派生目录（只读，跟随模块库目录）」说明文字实况
const list = await (await fetch("http://127.0.0.1:9251/json/list")).json();
const page = list.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0;
const pend = new Map();
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); }
};
const send = (method, params = {}) => new Promise((res) => {
  const mid = ++id; pend.set(mid, res);
  ws.send(JSON.stringify({ id: mid, method, params }));
});
const r = await send("Runtime.evaluate", {
  expression: `JSON.stringify({
    followLines: (document.body.innerText.match(/[^\\n]*跟随[^\\n]*/g) || []).slice(0, 3),
    secs: [...document.querySelectorAll('#tab-settings .settings-section')].map(s => s.textContent.trim().slice(0, 40))
  })`,
  returnByValue: true,
});
console.log(r.result.value);
process.exit(0);
