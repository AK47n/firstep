// 冒烟（reference-library-ui 系列，工单 02–05）：参考文件库页 UI——表格精修 + 客户端
// 即时检索/排序/统计 / 详情弹窗（元数据 + 磁盘实况文件清单）/ 编辑弹窗（改元数据 +
// 文件增删，一次 PUT）/ 悬空锚定警示（行内 ⚠ + 统计红段 + 过滤 + 编辑闭环）/
// 录入表单三分区折叠 + 视觉收尾。
//
// 重写说明（2026-09-09 第八轮「未完成」第 1 项）：本脚本写于前端阶段 2 ES 模块化
// **之前**，就绪判据与断言直接求值 `refEntryCache` / `refUI` / `refFilterContext()` /
// `refTopicKeys` / `kitVocabulary` / `loadReferences()` 等**模块作用域名**——模块化后
// 不再挂全局（`app.js` 规则 3：不挂 window 桥），求值抛错 → 就绪判据恒假 → 脚本退出
// 「页面未就绪」。本轮按已绿的 `.scratch/master-library-ui-2/smoke.mjs` 模板重写：
// cdp-harness（每支前重建标签页 + 自动应答 beforeunload + 命令超时）+ 数据取真实端点
// + 期望值由**页面内 `import()` 取纯件**现算 + 就绪/断言全部用 DOM 可观察事实；
// 需要触发重渲染时调 ui 模块的**导出**函数（`/js/ui/reference.js` → `loadReferences`
// / `loadKitVocabulary`；`/js/ui/files.js` → `addFileRow`）。
// 真实库卫生：只真写**临时条目**（标题前缀「冒烟临时-」/「冒烟悬空-」），每段 finally
// 里 DELETE 清理并服务器直查零残留；其余 169 条真实条目零触碰。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const PAGE_URL = "http://127.0.0.1:8000/";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await rebuildTab({ port: CDP, pageUrl: PAGE_URL, settleMs: 2000 });
const c = await connect({ port: CDP, pageUrl: PAGE_URL, timeoutMs: 20000 });
await c.cdp("Page.enable");
const Eval = (expr) => c.Eval(expr);

// 页面内探针命名空间（仅本次运行时注入，不落产品代码）：纯件 + ui 导出 + 真实数据。
// 悬空判定词表与页面同源：topicKeys = /api/topics 的 key；kits = /api/modules 各平台 kit 去重。
const boot = () => Eval(`(async () => {
  const [core, fx] = await Promise.all([import('/js/fx/core.js'), import('/js/fx/reference.js')]);
  const ui = { ref: await import('/js/ui/reference.js'), files: await import('/js/ui/files.js') };
  const topics = await (await fetch('/api/topics')).json();
  const modules = await (await fetch('/api/modules')).json();
  window.__probe = { core, fx, ui,
    refs: await (await fetch('/api/references')).json(),
    topicKeys: (Array.isArray(topics) ? topics : []).map((t) => t.key).filter(Boolean),
    kits: [...new Set(modules.flatMap((m) =>
      Object.values(m.platforms || {}).map((p) => p.kit).filter(Boolean)))].sort(),
    reload: async () => {
      window.__probe.refs = await (await fetch('/api/references')).json();
      await window.__probe.ui.ref.loadReferences();
      return window.__probe.refs.length;
    } };
  return window.__probe.refs.length;
})()`);

await boot();
const ready = await c.ready(`document.readyState === 'complete'
  && !!document.getElementById('tab-reference') && !!document.getElementById('ref-rows')
  && !!window.__probe && Array.isArray(window.__probe.refs)`, 20000);
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};
// 期望值单源 = 页面内纯件 + 真实端点数据（悬空判定的词表与页面同源）
const expect = (expr) => Eval(`(() => { const P = window.__probe; const refs = P.refs; const fx = P.fx;
  const { refFilterEntries, refDanglingAnchors, refSortEntries, refStats, refStatsText, refMatchFiles } = fx;
  const { formatSize } = P.core;
  const ctx = { topicKeys: P.topicKeys, kitVocab: P.kits };
  return (${expr}); })()`);

// 切「参考文件库」tab（host 分发器：loadReferences + loadKitVocabulary + loadTopicTypes）
const openTab = async (timeout = 20000) => {
  const n = await Eval(`window.__probe.refs.length`);
  await Eval(`(() => {
    const tab = [...document.querySelectorAll('nav button')].find((b) => b.dataset.tab === 'reference');
    if (tab) tab.click();
    return !!tab;
  })()`);
  return c.waitFor(`document.querySelectorAll('#ref-rows tr').length === ${n}`, timeout);
};
const total = await Eval(`window.__probe.refs.length`);
check("参考条目已加载（真实库全量行数）", await openTab(), "entries=" + total);

// ================= 工单 02：表格精修 + 检索 + 排序 + 统计 + 详情弹窗 =================
check("旧筛选区已移除（无 4 输入框 / 无搜索按钮）", await Eval(`!document.getElementById('ref-filter-title')
  && !document.getElementById('btn-ref-search') && !document.getElementById('btn-ref-search-clear')`));
check("工具栏元素齐全（搜索 / 排序 / 方向 / 清空 / 统计 / 两组 chips）", await Eval(`
  !!(document.getElementById('ref-filter') && document.getElementById('ref-sort')
    && document.getElementById('ref-sort-dir') && document.getElementById('ref-filter-clear')
    && document.getElementById('ref-stats') && document.getElementById('ref-platform-chips')
    && document.getElementById('ref-anchor-chips'))`));
// 防 id 冲突回归（评审 C1）：参考库搜索框 ref-filter 与生成页 picker 的 ref-search 各一
check("参考库搜索框 id 唯一（ref-filter，非生成页 picker 的 ref-search）", await Eval(`(() => {
  const ids = [...document.querySelectorAll('input[id]')].map((i) => i.id);
  return ids.filter((i) => i === 'ref-filter').length === 1
    && ids.filter((i) => i === 'ref-search').length === 1
    && document.querySelector('#tab-reference input#ref-filter') !== null; })()`));

const t02c = await Eval(`(() => {
  const table = document.querySelector('#tab-reference table');
  const th = document.querySelector('#tab-reference thead th');
  return { hasLibTable: !!table && table.classList.contains('lib-table'),
    thBg: th ? getComputedStyle(th).backgroundColor : null,
    ths: [...document.querySelectorAll('#tab-reference thead th')].map((t) => t.textContent.trim()) };
})()`);
check("表格带 lib-table 类", t02c.hasLibTable);
check("表头有底纹背景", !!t02c.thBg && t02c.thBg !== "rgba(0, 0, 0, 0)", "bg=" + t02c.thBg);
check("表头 7 列（标题/类型/题型/锚定/简介/体量/操作）",
  JSON.stringify(t02c.ths) === JSON.stringify(["标题", "类型", "题型", "锚定", "简介", "体量", "操作"]),
  t02c.ths.join("/"));

// 默认排序 = 最近更新降序（refUI 初值 mtime/desc，与 select 的 selected 项一致）
const t02e = await Eval(`(() => {
  const first = document.querySelector('#ref-rows tr');
  const titleTd = first.querySelector('.ref-title-cell');
  const descTd = first.querySelector('.desc-cell');
  const badge = first.querySelector('.badge');
  return {
    title: titleTd.textContent.trim().split('\\n')[0],
    titleTooltip: titleTd.getAttribute('title') || '',
    descTooltip: descTd ? (descTd.getAttribute('title') || '') : '',
    badgeClass: badge ? badge.className : '',
    btnView: (first.querySelector('[data-ref-view]') || {}).textContent || '',
    hasEdit: !!first.querySelector('[data-ref-edit]'),
    hasDel: !!first.querySelector('button.danger[data-ref-del]'),
    sortVal: document.getElementById('ref-sort').value,
    dirText: document.getElementById('ref-sort-dir').textContent,
  };
})()`);
const expFirstRef = await expect(`(() => { const e = refSortEntries(refs, { by: 'mtime', dir: 'desc' })[0];
  return { title: e.title }; })()`);
check("默认排序 = 最近更新降序（select 值 + 方向按钮文案）",
  t02e.sortVal === "mtime" && t02e.dirText.includes("↓"), `${t02e.sortVal} / ${t02e.dirText}`);
check("首行 = 纯件默认排序首条（标题 + 全量 tooltip / 简介 tooltip）",
  t02e.title === expFirstRef.title && t02e.titleTooltip.length > 0,
  `${t02e.title} vs ${expFirstRef.title}`);
check("首行锚定徽章（ref-topic / ref-kit / ref-none）",
  /badge ref-(topic|kit|none)/.test(t02e.badgeClass), t02e.badgeClass);
check("操作列三入口（详情 / 编辑 / danger 删除）",
  t02e.btnView === "详情" && t02e.hasEdit && t02e.hasDel, `${t02e.btnView}`);

const expStatsAll = await expect(`refStatsText(refStats(refFilterEntries(refs,
  { q: '', platform: '', anchorKind: '', dangling: false, topicKeys: ctx.topicKeys, kitVocab: ctx.kitVocab }), ctx))`);
check("统计条 = 全量纯件口径（平台 / 锚定 / 总体积）", await Eval(`
  document.getElementById('ref-stats').textContent.includes(${JSON.stringify(expStatsAll)})`), expStatsAll);

// ---- 关键字即时过滤（防抖 150ms）+ 命中行首条与纯件一致 ----
const qProbe = await Eval(`String(window.__probe.refs[0].title || '').slice(0, 4)`);
const t02g = await Eval(`(async () => {
  const inp = document.getElementById('ref-filter');
  inp.value = ${JSON.stringify(qProbe)};
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  const immediate = document.querySelectorAll('#ref-rows tr').length;
  await new Promise((r) => setTimeout(r, 500));
  const rows = [...document.querySelectorAll('#ref-rows tr')];
  return { immediate, n: rows.length,
    firstTitle: rows.length ? rows[0].querySelector('.ref-title-cell').textContent.trim().split('\\n')[0] : null };
})()`);
const expQ = await expect(`(() => {
  const list = refFilterEntries(refs, { q: ${JSON.stringify(qProbe)}, platform: '', anchorKind: '', topicKeys: ctx.topicKeys, kitVocab: ctx.kitVocab });
  return { n: list.length, first: list.length ? list[0].title : null }; })()`);
check("关键字过滤行数 = 纯件期望，且首行 = 期望首条",
  t02g.n === expQ.n && t02g.firstTitle === expQ.first, `n=${t02g.n}/${expQ.n} first=${t02g.firstTitle}`);
check("防抖 150ms 生效（派发 input 后当帧不重渲染）", t02g.immediate === total, `immediate=${t02g.immediate}`);

// ---- 平台 chip（mspm0）过滤 + 统计联动 ----
await Eval(`document.getElementById('ref-filter-clear').click()`);
await sleep(250);
const t02h = await Eval(`(async () => {
  const chip = [...document.querySelectorAll('#ref-platform-chips .lib-chip')]
    .find((b) => b.dataset.refChip === 'mspm0');
  if (!chip) return { skipped: true };
  chip.click();
  await new Promise((r) => setTimeout(r, 300));
  const on = document.querySelector('#ref-platform-chips .lib-chip.on');
  return { skipped: false, n: document.querySelectorAll('#ref-rows tr').length,
    onVal: on ? on.dataset.refChip : null,
    statsText: document.getElementById('ref-stats').textContent };
})()`);
if (!t02h.skipped) {
  const expMspm0 = await expect(`(() => {
    const list = refFilterEntries(refs, { q: '', platform: 'mspm0', anchorKind: '', topicKeys: ctx.topicKeys, kitVocab: ctx.kitVocab });
    return { n: list.length, stats: refStatsText(refStats(list, ctx)) }; })()`);
  check("平台 chip（mspm0）过滤 = 纯件期望 + on 态",
    t02h.n === expMspm0.n && t02h.onVal === "mspm0", `n=${t02h.n}/${expMspm0.n} on=${t02h.onVal}`);
  check("统计条随过滤联动 = 纯件期望（含悬空段口径）",
    t02h.statsText.includes(expMspm0.stats), t02h.statsText.trim().slice(0, 46));
  await Eval(`document.querySelector('#ref-platform-chips .lib-chip.on').click()`);
  await sleep(250);
} else {
  check("平台 chip 过滤（无 mspm0 条目，跳过）", true);
}

// ---- 锚定类型 chip（未锚定）过滤 ----
const t02i = await Eval(`(async () => {
  const chip = [...document.querySelectorAll('#ref-anchor-chips .lib-chip')]
    .find((b) => b.dataset.refChip === 'none');
  if (!chip) return { skipped: true };
  chip.click();
  await new Promise((r) => setTimeout(r, 300));
  const out = { skipped: false, n: document.querySelectorAll('#ref-rows tr').length,
    allNone: [...document.querySelectorAll('#ref-rows .badge')].every((b) => b.className.includes('ref-none')),
    onVal: (document.querySelector('#ref-anchor-chips .lib-chip.on') || {}).dataset?.refChip };
  document.getElementById('ref-filter-clear').click();
  await new Promise((r) => setTimeout(r, 300));
  out.restored = document.querySelectorAll('#ref-rows tr').length;
  return out;
})()`);
if (!t02i.skipped) {
  const expNone = await expect(`refFilterEntries(refs, { q: '', platform: '', anchorKind: 'none',
    topicKeys: ctx.topicKeys, kitVocab: ctx.kitVocab }).length`);
  check("锚定 chip（未锚定）过滤：行数 = 纯件期望且全为未锚定徽章",
    t02i.n === expNone && t02i.allNone && t02i.onVal === "none", `n=${t02i.n}/${expNone}`);
  check("清空过滤恢复全量", t02i.restored === total, `${t02i.restored} vs ${total}`);
} else {
  check("锚定 chip 过滤（跳过）", true);
}

// ---- 排序（体量）：默认方向降序 → 首行 = 纯件首条；再点方向 → 升序 ----
const t02j = await Eval(`(async () => {
  const firstTitle = () => { const tr = document.querySelector('#ref-rows tr');
    return tr ? tr.querySelector('.ref-title-cell').textContent.trim().split('\\n')[0] : null; };
  const sel = document.getElementById('ref-sort');
  sel.value = 'size';
  sel.dispatchEvent(new Event('change', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 300));
  const descFirst = firstTitle();
  document.getElementById('ref-sort-dir').click();
  await new Promise((r) => setTimeout(r, 300));
  return { descFirst, ascFirst: firstTitle(), dirText: document.getElementById('ref-sort-dir').textContent };
})()`);
const expSize = await expect(`(() => { const d = refSortEntries(refs, { by: 'size', dir: 'desc' })[0];
  const a = refSortEntries(refs, { by: 'size', dir: 'asc' })[0];
  return { desc: d.title, asc: a.title }; })()`);
check("体量降序首行 = 纯件期望", t02j.descFirst === expSize.desc, `${t02j.descFirst} vs ${expSize.desc}`);
check("方向切换（↑ 升序）首行 = 纯件期望 + 按钮文案跟随",
  t02j.ascFirst === expSize.asc && t02j.dirText.includes("↑"), `${t02j.ascFirst} / ${t02j.dirText}`);
await Eval(`(() => { const s = document.getElementById('ref-sort');
  s.value = 'mtime'; s.dispatchEvent(new Event('change', { bubbles: true })); })()`);   // 回默认
await sleep(300);

// ---- 空态（过滤无结果）与清空恢复 ----
const t02n = await Eval(`(async () => {
  const inp = document.getElementById('ref-filter');
  inp.value = 'ZZZZ无此词ZZZZ';
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 500));
  const empty = document.querySelector('#ref-rows .empty-state');
  const out = { title: (empty?.querySelector('.es-title') || {}).textContent || '',
    hint: (empty?.querySelector('.es-hint') || {}).textContent || '' };
  document.getElementById('ref-filter-clear').click();
  await new Promise((r) => setTimeout(r, 300));
  out.restored = document.querySelectorAll('#ref-rows tr').length;
  return out;
})()`);
check("过滤无结果空态（「没有匹配的参考条目」+ 指向清空过滤）",
  t02n.title.includes("没有匹配") && t02n.hint.includes("清空过滤"), t02n.title);
check("空态清空后恢复全量", t02n.restored === total, `${t02n.restored} vs ${total}`);

// ---- 详情弹窗（元数据段 + 磁盘实况文件清单 + 过滤）----
const detailId = await Eval(`(() => {
  const e = window.__probe.refs.find((x) => (x.file_count || 0) > 0);
  return e ? e.id : null;
})()`);
if (detailId) {
  const detailSel = `#ref-rows [data-ref-view="${detailId}"]`;
  const t02l = await Eval(`(async () => {
    const btn = document.querySelector(${JSON.stringify(detailSel)});
    if (!btn) return { found: false };
    btn.click();
    await new Promise((r) => setTimeout(r, 800));
    const ov = document.querySelector('.ref-files-overlay');
    if (!ov) return { found: false };
    const meta = ov.querySelector('.ref-detail-meta');
    return {
      found: true, headText: ov.querySelector('.ref-files-head strong').textContent,
      title: meta.querySelector('.ref-detail-title').textContent,
      rows: meta.querySelectorAll('.ref-detail-row').length,
      listItems: ov.querySelectorAll('.ref-files-list li[data-path]').length,
      hasFilter: !!ov.querySelector('.ref-files-filter'),
      hasViewer: !!ov.querySelector('.ref-files-viewer'),
    };
  })()`);
  check("详情弹窗打开（遮罩 + 头部「参考条目详情」）",
    t02l.found && t02l.headText.includes("参考条目详情"), t02l.headText);
  check("元数据段：标题 + 5 行（编号/类型/锚定/简介/体量）+ 磁盘实况文件清单 + 过滤框",
    t02l.rows === 5 && t02l.listItems > 0 && t02l.hasFilter && t02l.hasViewer,
    `rows=${t02l.rows} items=${t02l.listItems}`);
  const t02m = await Eval(`(async () => {
    const ov = document.querySelector('.ref-files-overlay');
    const first = ov.querySelector('.ref-files-list li[data-path]');
    const needle = (first.dataset.path || '').slice(0, 5);
    const inp = ov.querySelector('.ref-files-filter');
    inp.value = needle;
    inp.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise((r) => setTimeout(r, 200));
    const total = ov.querySelectorAll('.ref-files-list li[data-path]').length;
    const visible = [...ov.querySelectorAll('.ref-files-list li[data-path]')]
      .filter((li) => li.style.display !== 'none').length;
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await new Promise((r) => setTimeout(r, 250));
    return { needle, visible, total, closedByEsc: document.querySelectorAll('.ref-files-overlay').length === 0 };
  })()`);
  check("详情文件过滤：可见数 ≥ 1 且 ≤ 总数",
    t02m.visible >= 1 && t02m.visible <= t02m.total, `vis=${t02m.visible}/${t02m.total} needle=${t02m.needle}`);
  check("Esc 关闭详情弹窗", t02m.closedByEsc);
} else {
  check("详情弹窗（库无带文件条目，跳过）", true);
}

// ================= 工单 03：编辑弹窗（改元数据 + 文件删除，一次 PUT） =================
// 临时条目流：add → edit → 持久化验证（页面 reload + GET 回读）→ delete；finally 兜底清理。
const TMP_TITLE = "冒烟临时-编辑条目";
const cleanupBy = async (prefix) => {
  try {
    return await Eval(`(async () => {
      const all = await (await fetch('/api/references')).json();
      const hit = all.filter((e) => (e.title || '').startsWith(${JSON.stringify(prefix)}));
      for (const e of hit) await fetch('/api/references/' + encodeURIComponent(e.id), { method: 'DELETE' });
      return hit.length;
    })()`);
  } catch { return -1; }
};
try {
  await cleanupBy(TMP_TITLE);   // 幂等：先清历史残留
  const tmpId = await Eval(`(async () => {
    const r = await fetch('/api/references', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: ${JSON.stringify(TMP_TITLE)}, type: '冒烟测试',
        description: '工单 03 冒烟专用，脚本结束后删除', anchor_kind: 'none', anchor_value: '',
        platform: 'any', files: { 'demo.txt': '冒烟临时文件' } }),
    });
    if (!r.ok) throw new Error('add 失败 ' + r.status + ' ' + (await r.text()));
    return (await r.json()).id;
  })()`);
  await Eval(`window.__probe.reload()`);
  await c.waitFor(`!!document.querySelector('#ref-rows [data-ref-edit="${tmpId}"]')`, 15000);
  await Eval(`document.querySelector('#ref-rows [data-ref-edit="${tmpId}"]').click()`);
  await c.waitFor(`!!document.querySelector('.lib-edit-overlay')`, 8000);
  // 文件清单是异步拉的（apiGet .../files），**保存按钮的事件绑定在其后**——
  // 必须等清单渲染完再交互，否则点击落在未接线的按钮上（静默无反应）
  await c.waitFor(`document.querySelectorAll('.lib-edit-overlay .ref-edit-files li').length > 0`, 8000);
  const t03a = await Eval(`(() => {
    const ov = document.querySelector('.lib-edit-overlay');
    return {
      head: (ov.querySelector('.ref-edit-id') || {}).textContent || '',
      title: (ov.querySelector('.ref-edit-title') || {}).value ?? null,
      kind: (ov.querySelector('.ref-edit-kind') || {}).value ?? null,
      desc: (ov.querySelector('.ref-edit-desc') || {}).value ?? null,
      hasSave: !!ov.querySelector('.ref-edit-save'),
      hasFiles: !!ov.querySelector('.ref-edit-files'),
      fileLis: ov.querySelectorAll('.ref-edit-files li').length,
      hasRm: ov.querySelectorAll('[data-edit-rm]').length,
      hasAddRow: !!ov.querySelector('.ref-edit-addrow'),
    };
  })()`);
  check("编辑弹窗打开，头部 = 条目 id", t03a.head === tmpId, t03a.head);
  check("预填标题 / 锚定（none）/ 简介", t03a.title === TMP_TITLE && t03a.kind === "none" && !!t03a.desc,
    `${t03a.title} / ${t03a.kind}`);
  check("保存按钮 + 文件清单段（磁盘实况 1 行 + 勾删框 + 加行入口）",
    t03a.hasSave && t03a.hasFiles && t03a.fileLis === 1 && t03a.hasRm === 1 && t03a.hasAddRow,
    `lis=${t03a.fileLis} rm=${t03a.hasRm}`);

  const NEW_TITLE = TMP_TITLE + "-改";
  await Eval(`(() => {
    const ov = document.querySelector('.lib-edit-overlay');
    ov.querySelector('.ref-edit-title').value = ${JSON.stringify(NEW_TITLE)};
    ov.querySelector('.ref-edit-desc').value = '工单 03 已编辑（冒烟验证持久化）';
    const rm = ov.querySelector('[data-edit-rm]');
    if (rm) rm.checked = true;
    ov.querySelector('.ref-edit-save').click();
  })()`);
  let t03b = { overlayGone: false, cacheTitle: null, rowTitle: null };
  for (let i = 0; i < 60; i++) {
    await sleep(200);
    t03b = await Eval(`(async () => {
      const all = await (await fetch('/api/references')).json();
      const e = all.find((x) => x.id === ${JSON.stringify(tmpId)});
      const btn = document.querySelector('#ref-rows [data-ref-edit="${tmpId}"]');
      return { overlayGone: document.querySelectorAll('.lib-edit-overlay').length === 0,
        cacheTitle: e ? e.title : null,
        rowTitle: btn ? btn.closest('tr').querySelector('.ref-title-cell').textContent.trim().split('\\n')[0] : null };
    })()`);
    if (t03b.overlayGone && t03b.cacheTitle === NEW_TITLE && t03b.rowTitle === NEW_TITLE) break;
  }
  check("保存成功：弹窗关闭 + GET 回读新标题 + 表格行即时刷新",
    t03b.overlayGone && t03b.cacheTitle === NEW_TITLE && t03b.rowTitle === NEW_TITLE, t03b.cacheTitle);
  const filesLeft = await Eval(`fetch('/api/references/${tmpId}/files').then((r) => r.json()).then((f) => f.length)`);
  check("勾选删除文件生效（磁盘实况端点 files 已空）", filesLeft === 0, "files=" + filesLeft);

  // 持久化：整页 reload 后 GET 回读仍为新标题（探针重新注入）
  await Eval(`window.__smokeMarker = 1`);
  await c.cdp("Page.reload", { ignoreCache: true });
  let backReady = false;
  for (let i = 0; i < 100 && !backReady; i++) {
    try { backReady = await Eval(`document.readyState === 'complete'`); } catch {}
    if (!backReady) await sleep(300);
  }
  await boot();
  const t03c = await Eval(`(async () => {
    const all = await (await fetch('/api/references')).json();
    const e = all.find((x) => x.id === ${JSON.stringify(tmpId)});
    return e ? e.title : null;
  })()`);
  check("刷新页面后编辑仍持久（服务器直查新标题）", t03c === NEW_TITLE, t03c);
} finally {
  await cleanupBy(TMP_TITLE);
}
check("临时条目已清理（真实库零残留，服务器直查）",
  (await Eval(`(async () => {
    const all = await (await fetch('/api/references')).json();
    return all.some((e) => (e.title || '').startsWith(${JSON.stringify(TMP_TITLE)})); })()`)) === false);

// 回到参考库 tab（reload 后需重新激活 + 重拉）
await Eval(`window.__probe.reload()`);
check("清理后回到参考库 tab 全量", await openTab(), "entries=" + (await Eval(`window.__probe.refs.length`)));

// ================= 工单 04：悬空锚定警示 =================
const t04a = await Eval(`(() => ({ topics: window.__probe.topicKeys.length, kits: window.__probe.kits.length }))()`);
check("悬空判定数据源就绪（赛题 key / kit 词表非空）", t04a.topics > 0 && t04a.kits > 0,
  `topics=${t04a.topics}, kits=${t04a.kits}`);

const t04b = await Eval(`(() => {
  const P = window.__probe;
  const exp = P.fx.refDanglingAnchors(P.refs, P.topicKeys, P.kits);
  const red = document.querySelector('#ref-stats [data-ref-dangling]');
  return { exp: exp.length,
    withTag: [...document.querySelectorAll('#ref-rows tr')].filter((tr) => tr.querySelector('.ref-dangling-tag')).length,
    hasRed: !!red, redText: red ? red.textContent : '' };
})()`);
check("行内 ⚠ 数 = 悬空条目数（纯件同源）", t04b.withTag === t04b.exp, `withTag=${t04b.withTag}, exp=${t04b.exp}`);
check("统计条红色悬空段：有悬空才渲染 + 计数一致",
  t04b.hasRed === (t04b.exp > 0) && (!t04b.hasRed || t04b.redText.includes(String(t04b.exp))),
  t04b.redText || "none");
if (t04b.hasRed) {
  const t04c = await Eval(`(async () => {
    document.querySelector('#ref-stats [data-ref-dangling]').click();
    await new Promise((r) => setTimeout(r, 350));
    const out = { n: document.querySelectorAll('#ref-rows tr').length };
    document.querySelector('#ref-stats [data-ref-dangling]').click();
    await new Promise((r) => setTimeout(r, 350));
    out.restored = document.querySelectorAll('#ref-rows tr').length;
    return out;
  })()`);
  check("点击红段：只显示悬空条目（行数 = 纯件悬空数）", t04c.n === t04b.exp, `n=${t04c.n}, exp=${t04b.exp}`);
  check("再点取消：恢复全量", t04c.restored === total, `${t04c.restored} vs ${total}`);
} else {
  check("空库降级分支：红段未渲染（跳过点击验证）", true);
}

// 编辑闭环：临时 topic 悬空条目 → ⚠ 出现 → 编辑改未锚定 → ⚠ 消失 → finally 清理
const D_TITLE = "冒烟悬空-临时条目";
try {
  await cleanupBy(D_TITLE);
  const dEntry = await Eval(`(async () => {
    let last = null;
    for (const av of ['1999Z', '2099Z', '2088Z', '1977Z']) {
      const r = await fetch('/api/references', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: ${JSON.stringify(D_TITLE)}, type: '冒烟测试',
          description: '悬空警示冒烟，脚本结束后删除', anchor_kind: 'topic', anchor_value: av,
          platform: 'any', files: { 'demo.txt': 'x' } }),
      });
      if (r.ok) return { id: (await r.json()).id, av };
      last = r.status;
    }
    throw new Error('所有候选悬空编号都被拒（最后 ' + last + '）');
  })()`);
  await Eval(`window.__probe.reload()`);
  let foundTag = false;
  for (let i = 0; i < 50 && !foundTag; i++) {
    foundTag = await Eval(`(() => {
      const btn = document.querySelector('#ref-rows [data-ref-edit="${dEntry.id}"]');
      return !!btn && !!btn.closest('tr').querySelector('.ref-dangling-tag');
    })()`);
    if (!foundTag) await sleep(200);
  }
  check("悬空临时条目行内 ⚠（topic 锚定不命中任何赛题 key）", foundTag, "anchor=" + dEntry.av);

  await Eval(`document.querySelector('#ref-rows [data-ref-edit="${dEntry.id}"]').click()`);
  await c.waitFor(`!!document.querySelector('.lib-edit-overlay')`, 8000);
  await c.waitFor(`document.querySelectorAll('.lib-edit-overlay .ref-edit-files li').length > 0`, 8000);
  await Eval(`(() => {
    const ov = document.querySelector('.lib-edit-overlay');
    const k = ov.querySelector('.ref-edit-kind');
    k.value = 'none';
    k.dispatchEvent(new Event('change', { bubbles: true }));
    ov.querySelector('.ref-edit-save').click();
  })()`);
  let gone = false;
  for (let i = 0; i < 60 && !gone; i++) {
    await sleep(200);
    gone = await Eval(`(() => {
      const btn = document.querySelector('#ref-rows [data-ref-edit="${dEntry.id}"]');
      return !!btn && !btn.closest('tr').querySelector('.ref-dangling-tag');
    })()`);
  }
  check("编辑改未锚定保存后 ⚠ 消失（警示闭环）", gone);
} finally {
  await cleanupBy(D_TITLE);
}
check("悬空临时条目已清理（服务器直查零残留）",
  (await Eval(`(async () => {
    const all = await (await fetch('/api/references')).json();
    return all.some((e) => (e.title || '').startsWith(${JSON.stringify(D_TITLE)})); })()`)) === false);

// 截图（工单 05 证据之一：折叠态）
mkdirSync(join(ROOT, ".scratch", "reference-library-ui"), { recursive: true });
await Eval(`document.getElementById('tab-reference').scrollIntoView({ block: 'start' })`);
await sleep(400);

// ================= 工单 05：录入表单三分区折叠 + 视觉收尾 =================
// 口径修订（commit 70a0c3e3「工单 07 录入/编辑绕路：模块与参考草稿按钮同线、
// **参考 3 区默认展开**、提交随区常驻」）：参考录入表单三段**默认全部展开**
// （入库按钮与草稿反馈都在默认可见区），工单原文的「默认 aria-expanded
// true/false/false」被该评审整改取代；此处按实现现状断言「默认三段全展开 +
// 每段可收起/再展开且收起不丢已填状态」。
const t05a = await Eval(`(() => {
  const sec = (id) => document.getElementById(id);
  const basic = sec('add-sec-ref-basic'), mat = sec('add-sec-ref-material'), plat = sec('add-sec-ref-platform');
  if (!basic || !mat || !plat) return { n: 0 };
  return { n: document.querySelectorAll('#tab-reference .add-section').length,
    allOpen: [basic, mat, plat].every((s) => !s.classList.contains('collapsed')),
    aria: [basic, mat, plat].map((s) => s.querySelector('.add-section-head').getAttribute('aria-expanded')).join(','),
    addBtnVisible: document.getElementById('btn-ref-add').offsetParent !== null,
    draftBtnVisible: document.getElementById('btn-ref-draft-desc').offsetParent !== null };
})()`);
check("录入表单三分区齐备且默认全展开（aria-expanded = true,true,true，入库/草稿按钮常驻可见）",
  t05a.n === 3 && t05a.allOpen && t05a.aria === "true,true,true"
    && t05a.addBtnVisible && t05a.draftBtnVisible, JSON.stringify(t05a));

const shotCollapsed = await c.cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(join(ROOT, ".scratch", "reference-library-ui", "05-form-collapsed.png"),
  Buffer.from(shotCollapsed.result.data, "base64"));

// 每段可收起 → aria-expanded=false → 再展开恢复（① 段示范 + 字段 DOM 不销毁）
const t05b = await Eval(`(async () => {
  const sec = document.getElementById('add-sec-ref-basic');
  const head = sec.querySelector('.add-section-head');
  document.getElementById('ref-title').value = 'probe-collapse';
  head.click();
  await new Promise((r) => setTimeout(r, 150));
  const out = { collapsed: sec.classList.contains('collapsed'),
    aria: head.getAttribute('aria-expanded'),
    bodyHidden: sec.querySelector('.add-section-body').offsetParent === null,
    titleKept: document.getElementById('ref-title').value };
  head.click();
  await new Promise((r) => setTimeout(r, 150));
  out.reopened = !sec.classList.contains('collapsed') && head.getAttribute('aria-expanded') === 'true';
  document.getElementById('ref-title').value = '';
  return out;
})()`);
check("① 段收起（aria-expanded=false + body 隐藏）→ 再展开恢复，已填标题保留",
  t05b.collapsed && t05b.aria === "false" && t05b.bodyHidden
    && t05b.titleKept === "probe-collapse" && t05b.reopened, JSON.stringify(t05b));

// 收起不丢状态：加文件行 → 收起 → 再展开 → 行数与基线一致（DOM 不销毁）
const t05c = await Eval(`(async () => {
  const rows = () => document.querySelectorAll('#ref-files .file-row').length;
  const base = rows();
  document.querySelector('#btn-ref-add-file-row').click();
  const afterAdd = rows();
  document.querySelector('#add-sec-ref-material .add-section-head').click();
  await new Promise((r) => setTimeout(r, 150));
  document.querySelector('#add-sec-ref-material .add-section-head').click();
  await new Promise((r) => setTimeout(r, 150));
  return { base, afterAdd, afterRoundTrip: rows() };
})()`);
check("折叠往返不丢已填状态（文件行数 = 加行后，DOM 不销毁）",
  t05c.afterAdd === t05c.base + 1 && t05c.afterRoundTrip === t05c.afterAdd,
  `${t05c.base} → ${t05c.afterAdd} → ${t05c.afterRoundTrip}`);

// ③ 平台属性与入库：段落常驻展开 + 入库按钮真实可见（offsetParent 非空 = 可点击）
const t05d = await Eval(`(() => {
  const sec = document.getElementById('add-sec-ref-platform');
  const btn = sec.querySelector('#btn-ref-add');
  return { open: !sec.classList.contains('collapsed'), visible: !!btn && btn.offsetParent !== null };
})()`);
check("③ 平台属性与入库段展开且入库按钮可见", t05d.open && t05d.visible, JSON.stringify(t05d));

const shotExpanded = await c.cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(join(ROOT, ".scratch", "reference-library-ui", "05-form-expanded.png"),
  Buffer.from(shotExpanded.result.data, "base64"));

// AI 草稿反馈在②区、入库反馈在③区（就近可见——评审整改）
const t05e = await Eval(`(() => ({
  inMat: !!document.querySelector('#add-sec-ref-material #ref-draft-msg'),
  inPlat: !!document.querySelector('#add-sec-ref-platform #ref-add-msg'),
  draftBtnInMat: !!document.querySelector('#add-sec-ref-material #btn-ref-draft-desc'),
}))()`);
check("AI 草稿按钮与反馈在②区、入库反馈在③区（就近可见）",
  t05e.inMat && t05e.inPlat && t05e.draftBtnInMat, JSON.stringify(t05e));

// 还原表单：清掉临时文件行 → 恢复预置 1 行；三段回到默认全展开（避免污染复跑）
await Eval(`(() => {
  const box = document.getElementById('ref-files');
  [...box.querySelectorAll('.file-row')].forEach((r) => r.remove());
  window.__probe.ui.files.addFileRow(box);
  document.querySelectorAll('#tab-reference .add-section').forEach((sec) => {
    if (sec.classList.contains('collapsed')) sec.querySelector('.add-section-head').click();
  });
})()`);
await sleep(200);
check("表单状态复位（预置 1 文件行 + 三段回默认展开）", await Eval(`
  document.querySelectorAll('#ref-files .file-row').length === 1
  && [...document.querySelectorAll('#tab-reference .add-section')]
    .every((sec) => !sec.classList.contains('collapsed'))`));
console.log("05-form-collapsed.png / 05-form-expanded.png 已存档");

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
c.close();
process.exit(failed === 0 ? 0 : 1);
