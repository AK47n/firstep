// 诊断：确认 probe-02 选中的平台与当前角色/绑定状态（只读，不改页面）
const list = await (await fetch("http://127.0.0.1:9251/json/list")).json();
const page = list.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); }
};
const send = (method, params = {}) => new Promise((res) => {
  const mid = ++id; pending.set(mid, res);
  ws.send(JSON.stringify({ id: mid, method, params }));
});
const r = await send("Runtime.evaluate", {
  expression: `JSON.stringify({
    chosen: (document.querySelector('.platform-card.selected .name') || {}).textContent || null,
    cards: [...document.querySelectorAll('.platform-card')].map(c => ({ name: (c.querySelector('.name') || {}).textContent, disabled: c.classList.contains('disabled') })),
    offModules: [...document.querySelectorAll('.module-card.off')].map(c => c.dataset.add),
    steps: [...document.querySelectorAll('.step-nav .step-dot')].map(d => d.dataset.step + (d.classList.contains('done') ? '✓' : '')),
    badge: (() => { const b = document.getElementById('instance-gap-badge'); return b ? { hidden: b.classList.contains('hidden'), text: b.textContent } : null; })(),
    pinRoleItems: (document.getElementById('pin-role-items') || {}).textContent?.replace(/\\s+/g, ' ').trim().slice(0, 160) || null
  })`,
  returnByValue: true,
});
console.log(JSON.stringify(JSON.parse(r.result.value), null, 1));
process.exit(0);
