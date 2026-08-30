// 验收走查补探针：工单 22/23/24 各验收项（DOM 实况 + 纯函数渲染直验）
// 依赖：webapp 8000 + Chrome CDP 9251（probe-02 同一实例）。
const list = await (await fetch("http://127.0.0.1:9251/json/list")).json();
const page = list.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0;
const pending = new Map();
const jsErrors = [];
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); }
  if (m.method === "Runtime.exceptionThrown") jsErrors.push(m.params.exceptionDetails?.exception?.description || "exception");
};
const send = (method, params = {}) => new Promise((res) => {
  const mid = ++id; pending.set(mid, res);
  ws.send(JSON.stringify({ id: mid, method, params }));
});
const Eval = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error("eval 失败: " + (r.exceptionDetails.exception?.description || JSON.stringify(r.exceptionDetails)));
  return r.result?.value;
};
await send("Runtime.enable");
await send("Page.enable");
await send("Network.enable");
await send("Network.setCacheDisabled", { cacheDisabled: true });
await Eval(`localStorage.clear(); true`);
await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: "http://127.0.0.1:8000/?np=" + Date.now() });
let ready = false;
for (let i = 0; i < 120 && !ready; i++) {
  try { ready = await Eval(`document.readyState === 'complete' && !!document.getElementById('platforms')`); } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
await new Promise((r) => setTimeout(r, 1000));

// ---- 24-1：compact 态欢迎卡（纯函数渲染 + 真实按钮绑定 + 点击跳转） ----
const compact = await Eval(`(async () => {
  const app = await import('/js/app.js');
  app.setState({ ...app.state, api_configured: true });
  const w = await import('/js/ui/welcome.js');
  w.initWelcome();
  const slot = document.getElementById('welcome-card');
  const btns = [...slot.querySelectorAll('button')].map(b => b.id || b.textContent.trim());
  const go = document.getElementById('btn-welcome-compact-go');
  if (!go) return JSON.stringify({ ok: false, btns });
  go.click();
  const active = document.querySelector('section.page.active')?.id;
  return JSON.stringify({ ok: true, btns, activeTab: active, focused: document.activeElement?.id });
})()`);
console.log("24-1 compact:", compact);

// ---- 23-2：长跑屏幕「有问题？去问 AI」直达按钮存在性（三个页面） ----
const aiLinks = await Eval(`JSON.stringify({
  fixCenter: !!document.querySelector('#tab-generate [data-goto-global-chat]'),
  revise: !!document.querySelector('#revise-panel-revise [data-goto-global-chat]'),
  masterTab: (() => { document.querySelector('nav button[data-tab="master"]').click(); return !!document.querySelector('#tab-master [data-goto-global-chat]'); })()
})`);
console.log("23-2 aiLinks:", aiLinks);

// ---- 22-1：参考/PDF 默认排序（选中「按最近更新（默认）」） ----
const sorts = await Eval(`(async () => {
  document.querySelector('nav button[data-tab="reference"]').click();
  await new Promise(r => setTimeout(r, 800));
  const refVal = document.getElementById('ref-sort')?.value;
  const refSel = document.getElementById('ref-sort')?.selectedOptions?.[0]?.textContent;
  const refDir = document.getElementById('ref-sort-dir')?.textContent;
  document.querySelector('nav button[data-tab="pdf"]').click();
  await new Promise(r => setTimeout(r, 800));
  const pdfVal = document.getElementById('pdf-sort')?.value;
  const pdfSel = document.getElementById('pdf-sort')?.selectedOptions?.[0]?.textContent;
  const pdfDir = document.getElementById('pdf-sort-dir')?.textContent;
  return JSON.stringify({ refVal, refSel, refDir, pdfVal, pdfSel, pdfDir });
})()`);
console.log("22-1 sorts:", sorts);

// ---- 22-4：设置页库目录卡（5 目录：2 可编辑 + 3 只读派生 + 跟随说明） ----
const libdirs = await Eval(`(async () => {
  document.querySelector('nav button[data-tab="settings"]').click();
  await new Promise(r => setTimeout(r, 900));
  const ids = ['set-lib-dir', 'set-masters-dir', 'set-lib-dir-topic', 'set-lib-dir-reference', 'set-lib-dir-pdf'];
  const rows = ids.map(i => { const el = document.getElementById(i); return el ? { id: i, ro: el.readOnly, el: el.tagName } : { id: i, missing: true }; });
  const follow = [...document.querySelectorAll('#tab-settings')].length
    ? (document.body.innerText.match(/跟随模块库目录|同级（topics \\/ references \\/ sources\\/materials）/g) || []).slice(0, 2)
    : [];
  return JSON.stringify({ rows, follow });
})()`);
console.log("22-4 libdirs:", libdirs);

// ---- 24-3：宽屏 1920×1080 无溢出（生成页 + 设置页） ----
await send("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
await send("Page.reload", { ignoreCache: true });
await new Promise((r) => setTimeout(r, 1500));
const wide1 = await Eval(`JSON.stringify({
  sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
  active: document.querySelector('section.page.active')?.id,
  overflow: Array.from(document.querySelectorAll('section.page.active *')).filter(el => el.getBoundingClientRect().right > window.innerWidth + 2).slice(0, 3).map(el => el.id || el.className)
})`);
await Eval(`document.querySelector('nav button[data-tab="settings"]').click(); true`);
await new Promise((r) => setTimeout(r, 900));
const wide2 = await Eval(`JSON.stringify({
  sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
  active: document.querySelector('section.page.active')?.id,
  overflow: Array.from(document.querySelectorAll('section.page.active *')).filter(el => el.getBoundingClientRect().right > window.innerWidth + 2).slice(0, 3).map(el => el.id || el.className)
})`);
console.log("24-3 wide-generate:", wide1);
console.log("24-3 wide-settings:", wide2);

console.log("jsErrors:", jsErrors.length ? jsErrors.slice(0, 5).join("\n") : "none");
process.exit(0);
