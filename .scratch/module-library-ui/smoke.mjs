// 冒烟（module-library-ui 系列）：模块库页 UI。每张工单追加检查项。
// 零依赖：node 内置 fetch + WebSocket 直连 Chrome CDP（9251）；webapp 8000 提供真实 /api/modules。
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
  } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
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
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};

let ready = false;
await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('tab-library')
      && typeof state !== 'undefined' && state && Array.isArray(state.modules)`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};

// ---- 切「模块库」tab ----
await Eval(`(() => {
  const tab = [...document.querySelectorAll('nav button, header button, .nav button')]
    .find((b) => b.textContent.trim() === '模块库');
  if (tab) tab.click();
  return !!tab;
})()`);
await new Promise((r) => setTimeout(r, 800));

// ---- 工单 01：表格视觉令牌化 ----
const t01 = await Eval(`(() => {
  const table = document.querySelector('#tab-library table');
  const rows = document.querySelectorAll('#lib-rows tr').length;
  const modules = (state.modules || []).length;
  const first = document.querySelector('#lib-rows td.slug');
  const desc = document.querySelector('#lib-rows td.desc-cell');
  const th = document.querySelector('#tab-library thead th');
  const btnDel = document.querySelector('#lib-rows button.danger');
  const btnEdit = document.querySelector('#lib-rows [data-edit-desc]');
  return {
    hasLibTable: !!(table && table.classList.contains('lib-table')),
    rows, modules,
    slugIsMono: first ? getComputedStyle(first).fontFamily.includes('mono') : false,
    descTitleGlobal: desc ? (desc.title || '').length > 0 : false,
    descEllipsis: desc ? getComputedStyle(desc).textOverflow === 'ellipsis' : false,
    thBg: th ? getComputedStyle(th).backgroundColor : null,
    hasDangerDelete: !!btnDel,
    hasEditBtn: !!btnEdit,
    rowBg1: (() => {
      const trs = document.querySelectorAll('#lib-rows tr');
      return trs.length ? getComputedStyle(trs[0]).backgroundColor : null;
    })(),
    rowBg2: (() => {
      const trs = document.querySelectorAll('#lib-rows tr');
      return trs.length > 1 ? getComputedStyle(trs[1]).backgroundColor : null;
    })(),
  };
})()`);
check("表格带 lib-table 类", t01.hasLibTable);
check("行数 = 模块数", t01.rows === t01.modules, `rows=${t01.rows}, modules=${t01.modules}`);
check("slug 等宽字体", t01.slugIsMono);
check("简介列 title 全文（截断可悬停）", t01.descTitleGlobal);
check("简介列 ellipsis 截断", t01.descEllipsis);
check("表头有底纹背景", !!t01.thBg && t01.thBg !== "rgba(0, 0, 0, 0)", "bg=" + t01.thBg);
check("操作列：改简介 + danger 删除", t01.hasEditBtn && t01.hasDangerDelete);
check("无新增斑马纹（相邻行背景一致且透明）", t01.rowBg1 === t01.rowBg2 && t01.rowBg1 === "rgba(0, 0, 0, 0)", `${t01.rowBg1} vs ${t01.rowBg2}`);

console.log(failed === 0 ? "SMOKE ALL PASS" : `SMOKE FAILED (${failed})`);
process.exit(failed === 0 ? 0 : 1);
