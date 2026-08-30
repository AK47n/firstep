// probe-narrow-settings.mjs — 窄屏响应式冒烟（补：设置页）：
// 两档视口 → 免缓存重载 → 点设置页签 → 横向溢出检查（与 probe-narrow 同口径）。
const list = await (await fetch("http://127.0.0.1:9251/json/list")).json();
const page = list.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
let id = 0;
const pending = new Map();
const send = (method, params = {}) => new Promise((res) => {
  const mid = ++id; pending.set(mid, res);
  ws.send(JSON.stringify({ id: mid, method, params }));
});
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); }
};
await new Promise((r) => (ws.onopen = r));
await send("Network.enable");
await send("Network.setCacheDisabled", { cacheDisabled: true });
for (const [w, h] of [[900, 800], [720, 900]]) {
  await send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: false });
  await send("Page.reload", { ignoreCache: true });
  await new Promise((r) => setTimeout(r, 1200));
  await send("Runtime.evaluate", { expression:
    'document.querySelector(\'nav button[data-tab="settings"]\').click()', returnByValue: true });
  await new Promise((r) => setTimeout(r, 900));
  const res = await send("Runtime.evaluate", { expression:
    'JSON.stringify({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,'
    + ' bodySw: document.body.scrollWidth, active: (document.querySelector("section.page.active")||{}).id,'
    + ' overflowEls: Array.from(document.querySelectorAll("section.page.active *"))'
    + '.filter(el => el.getBoundingClientRect().right > window.innerWidth + 2).slice(0,5).map(el => el.id || el.className)})',
    returnByValue: true });
  console.log(w + "x" + h + ":", res.result.value);
}
await send("Emulation.clearDeviceMetricsOverride");
process.exit(0);
