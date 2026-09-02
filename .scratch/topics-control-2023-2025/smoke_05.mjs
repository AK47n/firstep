// 工单 topics-control-2023-2025/05 步骤 2：CDP 前端冒烟——题库分类筛选 +
// 新题详情 + 编辑表单分类下拉 + 保存透出（同值保存：无 manifest 变更，
// 库内自动提交「无变更跳过」，零副作用——遗留文件已 stash、revise-backups
// 已 exclude）。
// 零依赖：node 内置 fetch + WebSocket 直连 Chrome CDP（9251）；webapp 8000。
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const CDP = 9251;

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
  } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page" && t.url.includes("127.0.0.1:8000"));
if (!page) { console.error("无 webapp 页目标", targets.map((t) => t.url)); process.exit(1); }
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

await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('tab-topic')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};

// ---- 切「赛题库」tab ----
await Eval(`(() => {
  const tab = [...document.querySelectorAll('nav button')]
    .find((b) => b.textContent.trim() === '赛题库');
  if (tab) tab.click();
  return !!tab;
})()`);
let cardCount = 0;
for (let i = 0; i < 60; i++) {
  cardCount = await Eval(`document.querySelectorAll('#topic-grid .topic-card').length`);
  if (cardCount >= 20) break;
  await new Promise((r) => setTimeout(r, 250));
}

check("赛题列表已加载（20 条）", cardCount === 20, "cards=" + cardCount);

// ---- 分类筛选下拉 ----
const catOpts = await Eval(`(() => {
  const sel = document.getElementById('topic-category');
  return sel ? [...sel.options].map((o) => o.value + ':' + o.textContent.trim()) : [];
})()`);
check("分类筛选下拉存在（全部/控制题/其他）",
  catOpts.length === 3 && catOpts[0] === ":全部" && catOpts.includes("control:控制题") && catOpts.includes("other:其他"),
  JSON.stringify(catOpts));

// ---- 筛选「控制题」：出现 5 新题、无 2026A（other）----
await Eval(`(() => {
  const sel = document.getElementById('topic-category');
  sel.value = 'control';
  sel.dispatchEvent(new Event('change'));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 500));
const shown = await Eval(`[...document.querySelectorAll('#topic-grid [data-topic-view]')].map((b) => b.dataset.topicView)`);
for (const k of ["2023E", "2023G", "2023I", "2025E", "2025H"]) {
  check("筛选「控制题」出现 " + k, shown.includes(k), "共 " + shown.length + " 张卡片");
}
check("筛选「控制题」无 other 题（2026A/B/C/F/G）",
  !["2026A", "2026B", "2026C", "2026F", "2026G"].some((k) => shown.includes(k)),
  JSON.stringify(shown));
check("筛选后卡片数为 15（control 全量）", shown.length === 15, "cards=" + shown.length);

// ---- 2023E 详情 ----
await Eval(`document.querySelector('#topic-grid [data-topic-view="2023E"]').click()`);
for (let i = 0; i < 40; i++) {
  if (await Eval(`!!document.querySelector('.topic-modal')`)) break;
  await new Promise((r) => setTimeout(r, 250));
}
check("2023E 详情弹窗打开", await Eval(`!!document.querySelector('.topic-modal')`));
check("详情题面含题名与一、任务",
  await Eval(`document.querySelector('.topic-modal .topic-detail-problem').textContent.includes('运动目标控制与自动追踪系统')
    && document.querySelector('.topic-modal .topic-detail-problem').textContent.includes('一、 任务')`));
check("详情「分类」行显示控制题",
  await Eval(`document.querySelector('.topic-modal').textContent.includes('分类') && document.querySelector('.topic-modal').textContent.includes('控制题')`));
await new Promise((r) => setTimeout(r, 1500));
const pagesState = await Eval(`(() => {
  const box = document.querySelector('.topic-modal [data-topic-pages]');
  if (!box) return 'no-box';
  const imgs = box.querySelectorAll('img').length;
  const txt = box.textContent.trim();
  return (imgs > 0 ? 'imgs=' + imgs : 'text=' + txt.slice(0, 30));
})()`);
check("详情页图区已渲染", !pagesState.startsWith("text=页图加载中") && !pagesState.startsWith("no-box"), pagesState);

// ---- 编辑表单分类下拉 ----
await Eval(`document.querySelector('.topic-modal [data-topic-edit]').click()`);
for (let i = 0; i < 40; i++) {
  if (await Eval(`!!document.querySelector('.topic-edit-category')`)) break;
  await new Promise((r) => setTimeout(r, 250));
}
const editOpts = await Eval(`(() => {
  const sel = document.querySelector('.topic-edit-category');
  return sel ? { value: sel.value, opts: [...sel.options].map((o) => o.value) } : null;
})()`);
check("编辑表单分类下拉（control/other，当前 control）",
  editOpts && editOpts.value === "control" && editOpts.opts.includes("control") && editOpts.opts.includes("other"),
  JSON.stringify(editOpts));

// ---- 保存（同值 control：无 manifest 变更，自动提交「无变更跳过」）----
await Eval(`document.querySelector('[data-topic-save]').click()`);
for (let i = 0; i < 60; i++) {
  const gone = await Eval(`!document.querySelector('.topic-edit-category')`);
  if (gone) break;
  await new Promise((r) => setTimeout(r, 300));
}
check("保存后编辑弹窗关闭", await Eval(`!document.querySelector('.topic-edit-category')`));
await new Promise((r) => setTimeout(r, 1200));
const chipAfter = await Eval(`(() => {
  const card = [...document.querySelectorAll('#topic-grid [data-topic-view="2023E"]')][0];
  if (!card) return null;
  const host = card.closest('.topic-card') || card.parentElement;
  return (host && host.textContent.includes('控制题')) ? '控制题' : host.textContent.slice(0, 40);
})()`);
check("保存后 2023E 卡片 chip「控制题」", chipAfter === "控制题", String(chipAfter));
const meta = await Eval(`fetch('/api/topics/2023E').then((r) => r.json())`);
check("2023E 单条端点 category=control", meta && meta.category === "control", JSON.stringify(meta && meta.category));

console.log(failed ? `\n${failed} 项失败` : "\n全部 PASS");
process.exit(failed ? 1 : 0);
