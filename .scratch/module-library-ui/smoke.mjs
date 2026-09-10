// 冒烟（module-library-ui 系列，工单 01–07）：模块库页 UI——表格令牌化 / 工具栏
// 过滤排序统计 / 详情弹窗 / 悬空依赖警示 / 改简介模态 / 编辑弹窗 / 录入分区折叠。
//
// 重写说明（2026-09-09 第八轮「未完成」第 1 项）：本脚本写于前端阶段 2 ES 模块化
// **之前**，就绪判据与断言直接求值 `state.modules` / `libStats(...)` /
// `renderLibraryTable()` 等**模块作用域名**——模块化后这些名字不再挂全局
// （`app.js` 规则 3：不挂 window 桥），求值抛错 → 就绪判据恒假 → 脚本退出
// 「页面未就绪」。本轮按已绿的 `.scratch/master-library-ui-2/smoke.mjs` 模板重写：
//   ① `.scratch/cdp-harness.mjs`（每支前重建标签页 + 自动应答 beforeunload + 命令超时）；
//   ② 数据取真实端点（`fetch('/api/modules')`，不再读模块内缓存）；
//   ③ 期望值由**页面内 `import()` 取纯件**现算（`/js/fx/module.js` 等），与 DOM 比对；
//   ④ 就绪与断言全部用 **DOM 可观察事实**；需要触发渲染时调用 ui 模块的**导出**函数
//      （`import('/js/ui/library.js')` → `editModule`）。
// 零依赖：node 内置 fetch + WebSocket 直连 Chrome CDP（9251）；webapp 8000 提供真实库。
// 零真删零真导：删除入口只验弹窗开合（取消），编辑弹窗的失败路径用**内存假模块**
// （后端 404，不动真实库）；「改简介」保存只走确定性 400（空简介）不触发 AI 校验与写库。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const PAGE_URL = "http://127.0.0.1:8000/";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---- 连接：每支脚本前重建标签页（clean 页 = 无脏缓冲 = 不弹 beforeunload） ----
await rebuildTab({ port: CDP, pageUrl: PAGE_URL, settleMs: 2000 });
const c = await connect({ port: CDP, pageUrl: PAGE_URL, timeoutMs: 20000 });
await c.cdp("Page.enable");
const Eval = (expr) => c.Eval(expr);

// 页面内探针命名空间（仅本次运行时注入，不落产品代码）：纯件 + ui 导出 + 真实数据
await Eval(`(async () => {
  const [core, mod] = await Promise.all([import('/js/fx/core.js'), import('/js/fx/module.js')]);
  const app = await import('/js/app.js');
  const ui = { lib: await import('/js/ui/library.js'), files: await import('/js/ui/files.js') };
  window.__probe = { core, mod, app, ui, mods: await (await fetch('/api/modules')).json() };
  return window.__probe.mods.length;
})()`);

const ready = await c.ready(`document.readyState === 'complete'
  && !!document.getElementById('tab-library') && !!document.getElementById('lib-rows')
  && !!window.__probe && Array.isArray(window.__probe.mods)`, 20000);
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};
// 期望值单源 = 页面内纯件 + 真实端点数据（DOM 与纯函数同口径比对）
const expect = (expr) => Eval(`(() => { const P = window.__probe; const mods = P.mods;
  const { libStats, libStatsText, libFilterModules, libSortModules, danglingDependencies, formatSize } = P.mod;
  return (${expr}); })()`);

// ---- 切「模块库」tab（host 分发器会跑 loadLibrary → 真实端点全量） ----
const modTotal = await Eval(`window.__probe.mods.length`);
await Eval(`(() => {
  const tab = [...document.querySelectorAll('nav button')].find((b) => b.dataset.tab === 'library');
  if (tab) tab.click();
  return !!tab;
})()`);
const rowsLoaded = await c.waitFor(`document.querySelectorAll('#lib-rows tr').length === ${modTotal}`, 20000);
check("模块库列表已加载（真实库全量行数）", rowsLoaded, `rows=${modTotal}`);

// ================= 工单 01：表格视觉令牌化 =================
const t01 = await Eval(`(() => {
  const table = document.querySelector('#tab-library table');
  const first = document.querySelector('#lib-rows td.slug');
  const desc = document.querySelector('#lib-rows td.desc-cell');
  const th = document.querySelector('#tab-library thead th');
  const trs = [...document.querySelectorAll('#lib-rows tr')];
  const badge = document.querySelector('#lib-rows .badge');
  return {
    hasLibTable: !!table && table.classList.contains('lib-table'),
    slugIsMono: first ? getComputedStyle(first).fontFamily.includes('mono') : false,
    descTitle: desc ? (desc.title || '').length > 0 : false,
    descEllipsis: desc ? getComputedStyle(desc).textOverflow === 'ellipsis' : false,
    thBg: th ? getComputedStyle(th).backgroundColor : null,
    hasDangerDelete: !!document.querySelector('#lib-rows button.danger[data-del]'),
    hasEditBtn: !!document.querySelector('#lib-rows [data-edit-desc]'),
    hasEditMod: !!document.querySelector('#lib-rows [data-edit-mod]'),
    hasInfo: !!document.querySelector('#lib-rows [data-info]'),
    hasBadge: !!badge,
    // 徽章配色完整性（第十轮目视验收修）：裸 badge（无颜色变体）只有形状没有底色，
    // 夹在彩色平台胶囊之间像「没套样式的裸文字」。两条：① 每枚 badge 都带变体类；
    // ② 「内嵌母版」的变体必须真给出底色。
    badgeCls: [...document.querySelectorAll('#lib-rows .badge')].map((b) => b.className),
    embedBadgeBg: (() => {
      const b = [...document.querySelectorAll('#lib-rows .badge')]
        .find((x) => x.textContent.trim() === '内嵌母版');
      return b ? getComputedStyle(b).backgroundColor : null;
    })(),
    embedBadgeCls: (() => {
      const b = [...document.querySelectorAll('#lib-rows .badge')]
        .find((x) => x.textContent.trim() === '内嵌母版');
      return b ? b.className : null;
    })(),
    // 简介列截断判据（第十轮补）：DOM 文本 = 纯件同源截断（26 字符 + …），
    // 且与 title 全文不同（截断发生了）——旧断言只查 title 非空，截断本身没被验。
    descText: desc ? desc.textContent : null,
    descTitleText: desc ? desc.title : null,
    rowBg1: trs.length ? getComputedStyle(trs[0]).backgroundColor : null,
    rowBg2: trs.length > 1 ? getComputedStyle(trs[1]).backgroundColor : null,
  };
})()`);
check("表格带 lib-table 类", t01.hasLibTable);
check("slug 列等宽字体", t01.slugIsMono);
check("简介列全文 tooltip（截断可悬停）", t01.descTitle);
check("简介列 ellipsis 截断", t01.descEllipsis);
// 简介列截断判据（第十轮补）：旧断言只查 title 非空 —— 「截断」本身没被验。
// 实现现状（读 fx/module.js moduleRowHTML 第 503 行 + index.html `.desc-cell` 规则）：
// 单元格渲染**全文**（DOM 文本 = 端点 description，逐字节相等），截断由 CSS
// `overflow:hidden + white-space:nowrap + text-overflow:ellipsis` 完成
// —— 故机器判据 = 全文进 DOM/进 title + 三项计算样式齐 + 文本**确实溢出**
// （scrollWidth 明显大于 clientWidth，否则「截断」不可见，只是这一列恰好短）。
const descExpect = await Eval(`(async () => {
  const mods = window.__probe.mods;
  const first = [...document.querySelectorAll('#lib-rows tr')][0];
  const slug = first.querySelector('td.slug').textContent;
  const m = mods.find((x) => x.slug === slug);
  const d = first.querySelector('td.desc-cell');
  const cs = getComputedStyle(d);
  return { slug, apiDesc: String(m.description || ''), domText: d.textContent, domTitle: d.title,
    overflow: cs.overflow, whiteSpace: cs.whiteSpace, textOverflow: cs.textOverflow,
    scrollW: d.scrollWidth, clientW: d.clientWidth };
})()`);
check("简介列 DOM 文本/title = 端点全文（截断由 CSS 完成，非文本裁剪）",
  descExpect.domText === descExpect.apiDesc && descExpect.domTitle === descExpect.apiDesc
    && descExpect.apiDesc.length > 0,
  `slug=${descExpect.slug} 全文 ${descExpect.apiDesc.length} 字`);
check("简介列截断三件套齐 + 文本确实溢出（ellipsis 可见）",
  descExpect.overflow === "hidden" && descExpect.whiteSpace === "nowrap"
    && descExpect.textOverflow === "ellipsis" && descExpect.scrollW > descExpect.clientW * 2,
  `overflow=${descExpect.overflow} ws=${descExpect.whiteSpace} ellipsis=${descExpect.textOverflow} `
  + `scroll=${descExpect.scrollW} client=${descExpect.clientW}`);
check("表头有底纹背景", !!t01.thBg && t01.thBg !== "rgba(0, 0, 0, 0)", "bg=" + t01.thBg);
check("操作列四入口齐备（详情 / 改简介 / 编辑 / danger 删除）",
  t01.hasInfo && t01.hasEditBtn && t01.hasEditMod && t01.hasDangerDelete);
check("平台徽章在位（行内 badge）", t01.hasBadge);
check("每枚徽章都带颜色变体类（无裸 .badge = 无底色裸文字）",
  t01.badgeCls.length > 0 && t01.badgeCls.every((c) => /(^|\s)(plat|neutral)(\s|$)/.test(c)),
  `共 ${t01.badgeCls.length} 枚，异常=${JSON.stringify(t01.badgeCls.filter((c) => !/(^|\s)(plat|neutral)(\s|$)/.test(c)))}`);
check("「内嵌母版」徽章有中性底色（badge neutral 变体生效）",
  /(^|\s)neutral(\s|$)/.test(t01.embedBadgeCls || "")
    && !!t01.embedBadgeBg && t01.embedBadgeBg !== "rgba(0, 0, 0, 0)",
  `cls=${t01.embedBadgeCls} bg=${t01.embedBadgeBg}`);
check("无斑马纹（相邻行背景一致且透明）",
  t01.rowBg1 === t01.rowBg2 && t01.rowBg1 === "rgba(0, 0, 0, 0)", `${t01.rowBg1} vs ${t01.rowBg2}`);

// ================= 工单 02：工具栏与统计条 =================
const barEls = await Eval(`!!(document.getElementById('lib-search')
  && document.getElementById('lib-sort') && document.getElementById('lib-sort-dir')
  && document.getElementById('lib-filter-clear') && document.getElementById('lib-stats')
  && document.getElementById('lib-platform-chips') && document.getElementById('lib-status-chips'))`);
check("工具栏元素齐全（搜索 / 排序 / 方向 / 清空 / 统计 / 两组 chips）", barEls);

const t02 = await Eval(`(() => ({
  statsText: document.getElementById('lib-stats').textContent,
  platVals: [...document.querySelectorAll('#lib-platform-chips .lib-chip')].map((b) => b.dataset.libChip),
  statusVals: [...document.querySelectorAll('#lib-status-chips .lib-chip')].map((b) => b.dataset.libChip),
  rowSlugs: [...document.querySelectorAll('#lib-rows td.slug')].map((td) => td.textContent.trim()),
}))()`);
const expStats = await expect(`libStatsText(libStats(mods))`);
const expPlats = await expect(`Object.keys(libStats(mods).platforms)`);
const expFirstSlug = await expect(`libSortModules(libFilterModules(mods, { q: '', platform: '', status: '' }),
  { by: 'slug', dir: 'asc' })[0].slug`);
check("统计条 = 全量纯件口径（总数 / 平台 / 已验证 / 硬件绑定 / 互斥组）",
  t02.statsText.includes(expStats), t02.statsText);
check("平台 chips = 全部 + 库内平台（计数），首项为「全部」",
  t02.platVals[0] === "" && expPlats.every((p) => t02.platVals.includes(p)), t02.platVals.join(","));
check("状态 chips = 全部 / 已验证 / 未验证 / 硬件绑定",
  t02.statusVals.join(",") === ",verified,unverified,hardware_bound", t02.statusVals.join(","));
check("默认排序（slug 升序）首行 = 纯件期望", t02.rowSlugs[0] === expFirstSlug,
  `${t02.rowSlugs[0]} vs ${expFirstSlug}`);

// ---- 搜索：无关词 → 空结果态；真实 slug（大写）命中；清空 → 全量 ----
const slug0 = await Eval(`window.__probe.mods[0].slug`);
const search = await Eval(`(async () => {
  const input = document.getElementById('lib-search');
  input.value = 'zzz无关词zzz';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 250));
  const emptyRows = document.querySelectorAll('#lib-rows tr').length;
  const emptyTitle = (document.querySelector('#lib-rows .es-title') || {}).textContent || '';
  const emptyHint = (document.querySelector('#lib-rows .es-hint') || {}).textContent || '';
  input.value = ${JSON.stringify(slug0.slice(0, Math.min(4, slug0.length)).toUpperCase())};
  input.dispatchEvent(new Event('input', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 250));
  const hitSlugs = [...document.querySelectorAll('#lib-rows td.slug')].map((td) => td.textContent.trim());
  document.getElementById('lib-filter-clear').click();
  await new Promise((r) => setTimeout(r, 250));
  return { emptyRows, emptyTitle, emptyHint, hitSlugs,
    backRows: document.querySelectorAll('#lib-rows tr').length,
    inputCleared: document.getElementById('lib-search').value === '' };
})()`);
check("无关词 → 空结果态（仅 1 行占位 + 友好提示 + 指向清空过滤）",
  search.emptyRows === 1 && search.emptyTitle.includes("没有匹配的模块")
    && search.emptyHint.includes("清空过滤"), search.emptyTitle);
check("真实 slug（大写输入）命中且大小写不敏感",
  search.hitSlugs.includes(slug0), search.hitSlugs.slice(0, 3).join(","));
check("清空过滤：恢复全量行数 + 搜索框已清空",
  search.backRows === modTotal && search.inputCleared, `${search.backRows} vs ${modTotal}`);

// ---- 平台 chip：点击过滤（行数 = 纯件期望 + on 态）→ 再点取消 ----
const chips = await Eval(`(async () => {
  const plat = document.querySelector('#lib-platform-chips .lib-chip[data-lib-chip]:not([data-lib-chip=""])');
  if (!plat) return { skipped: true };
  const pv = plat.dataset.libChip;
  plat.click();
  await new Promise((r) => setTimeout(r, 250));
  const filteredRows = document.querySelectorAll('#lib-rows tr').length;
  const onEls = [...document.querySelectorAll('#lib-platform-chips .lib-chip.on')];
  const onVal = onEls.length === 1 ? onEls[0].dataset.libChip : null;
  document.querySelector('#lib-platform-chips .lib-chip.on').click();
  await new Promise((r) => setTimeout(r, 250));
  return { skipped: false, pv, filteredRows, onCount: onEls.length, onVal,
    clearedRows: document.querySelectorAll('#lib-rows tr').length };
})()`);
if (!chips.skipped) {
  const expPlatRows = await expect(`libFilterModules(mods, { q: '', platform: ${JSON.stringify(chips.pv)}, status: '' }).length`);
  check("平台 chip 过滤：行数 = 纯件期望 + 唯一 on 态",
    chips.filteredRows === expPlatRows && chips.onCount === 1 && chips.onVal === chips.pv,
    `${chips.filteredRows} vs ${expPlatRows} on=${chips.onVal}`);
  check("平台 chip 再点取消：恢复全量", chips.clearedRows === modTotal, `${chips.clearedRows} vs ${modTotal}`);
} else {
  check("平台 chip 过滤（库无平台数据，跳过）", true);
  check("平台 chip 取消（库无平台数据，跳过）", true);
}

// ---- 状态 chip（已验证）+ Esc 清空搜索 ----
const chips2 = await Eval(`(async () => {
  const b = document.querySelector('#lib-status-chips .lib-chip[data-lib-chip="verified"]');
  if (!b) return { skipped: true };
  b.click();
  await new Promise((r) => setTimeout(r, 250));
  const filteredRows = document.querySelectorAll('#lib-rows tr').length;
  const onEls = [...document.querySelectorAll('#lib-status-chips .lib-chip.on')];
  const onVal = onEls.length === 1 ? onEls[0].dataset.libChip : null;
  const input = document.getElementById('lib-search');
  input.value = 'zzz无关词zzz';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  await new Promise((r) => setTimeout(r, 250));
  return { skipped: false, filteredRows, onVal,
    escRows: document.querySelectorAll('#lib-rows tr').length,
    escOnVals: [...document.querySelectorAll('#lib-status-chips .lib-chip.on')].map((b) => b.dataset.libChip),
    escPlatOnVals: [...document.querySelectorAll('#lib-platform-chips .lib-chip.on')].map((b) => b.dataset.libChip) };
})()`);
if (!chips2.skipped) {
  const expVerified = await expect(`libFilterModules(mods, { q: '', platform: '', status: 'verified' }).length`);
  check("状态 chip（已验证）过滤：行数 = 纯件期望 + on 态",
    chips2.filteredRows === expVerified && chips2.onVal === "verified",
    `${chips2.filteredRows} vs ${expVerified}`);
  check("Esc 一键清空全部过滤（含 chips 复用）→ 恢复全量",
    chips2.escRows === modTotal
      && JSON.stringify(chips2.escOnVals) === JSON.stringify([""])
      && JSON.stringify(chips2.escPlatOnVals) === JSON.stringify([""]),
    `${chips2.escRows} vs ${modTotal} on=${chips2.escOnVals.join("|")}`);
} else {
  check("状态 chip 过滤（跳过）", true);
  check("Esc 清空（跳过）", true);
}

// ---- 排序：平台数降序，全行序列 = 纯件同参数全序列 ----
const sort = await Eval(`(async () => {
  const sel = document.getElementById('lib-sort');
  sel.value = 'platforms';
  sel.dispatchEvent(new Event('change', { bubbles: true }));
  document.getElementById('lib-sort-dir').click();   // asc → desc
  await new Promise((r) => setTimeout(r, 250));
  const rowsNow = [...document.querySelectorAll('#lib-rows td.slug')].map((td) => td.textContent.trim());
  const dirBtn = document.getElementById('lib-sort-dir').textContent;
  return { rowsNow, dirBtn };
})()`);
const expSeq = await expect(`libSortModules(mods, { by: 'platforms', dir: 'desc' }).map((m) => m.slug)`);
check("排序（平台数降序）：行序列与纯件完全一致",
  JSON.stringify(sort.rowsNow) === JSON.stringify(expSeq), `first=${sort.rowsNow[0]} exp=${expSeq[0]}`);
check("排序方向按钮文案已切换（↓ 降序）", sort.dirBtn.includes("↓"), sort.dirBtn);
await Eval(`(() => { const s = document.getElementById('lib-sort');
  s.value = 'slug'; s.dispatchEvent(new Event('change', { bubbles: true }));
  document.getElementById('lib-sort-dir').click(); })()`);   // 还原 asc
await sleep(250);

// ================= 工单 03：行「详情」→ 全量信息弹窗 =================
const infoSlug = await Eval(`(document.querySelector('#lib-rows [data-info]') || {}).dataset?.info || null`);
if (infoSlug) {
  const expPlatsN = await expect(`Object.keys(mods.find((m) => m.slug === ${JSON.stringify(infoSlug)}).platforms || {}).length`);
  await Eval(`document.querySelector('#lib-rows [data-info]').click()`);
  await c.waitFor(`!!document.querySelector('.module-info-overlay')`, 5000);
  const d03 = await Eval(`(() => {
    const ov = document.querySelector('.module-info-overlay');
    return {
      count: document.querySelectorAll('.module-info-overlay').length,
      title: (ov.querySelector('.module-info-title .slug') || {}).textContent || '',
      plats: ov.querySelectorAll('.module-info-platforms .mi-plat').length,
      off: !!ov.querySelector('.module-info-off'),
      z: { ov: Number(getComputedStyle(ov).zIndex), hd: Number(getComputedStyle(document.querySelector('header')).zIndex) },
      drift: (() => { const md = ov.querySelector('.module-info-modal');
        if (!md) return -1; const r = md.getBoundingClientRect();
        return Math.round(Math.abs((r.top + r.bottom) / 2 - window.innerHeight / 2)); })(),
    };
  })()`);
  check("点「详情」→ 弹窗出现（替换式唯一）", d03.count === 1, `overlay=${d03.count}`);
  check("弹窗标题 = 该行 slug", d03.title === infoSlug, `${d03.title} vs ${infoSlug}`);
  check("无平台上下文：全部平台分段展示（无 off 提示）",
    d03.plats === expPlatsN && !d03.off, `plats=${d03.plats}/${expPlatsN}`);
  check("遮罩层级高于置顶目录", d03.z.ov > d03.z.hd, `overlay=${d03.z.ov} header=${d03.z.hd}`);
  check("弹窗垂直居中（±60px）", d03.drift >= 0 && d03.drift <= 60, `drift=${d03.drift}px`);

  await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))`);
  await c.waitFor(`!document.querySelector('.module-info-overlay')`, 4000);
  check("Esc 关闭弹窗（无残留）", await Eval(`document.querySelectorAll('.module-info-overlay').length === 0`));

  await Eval(`document.querySelector('#lib-rows [data-info]').click()`);
  await c.waitFor(`!!document.querySelector('.module-info-overlay')`, 5000);
  await Eval(`document.querySelector('.module-info-overlay').dispatchEvent(new MouseEvent('click', { bubbles: true }))`);
  await c.waitFor(`!document.querySelector('.module-info-overlay')`, 4000);
  check("遮罩点击关闭弹窗", await Eval(`document.querySelectorAll('.module-info-overlay').length === 0`));

  await Eval(`document.querySelector('#lib-rows [data-info]').click()`);
  await c.waitFor(`!!document.querySelector('.module-info-overlay')`, 5000);
  await Eval(`document.querySelector('.module-info-overlay .ref-files-close').click()`);
  await c.waitFor(`!document.querySelector('.module-info-overlay')`, 4000);
  check("右上 ✕ 关闭弹窗", await Eval(`document.querySelectorAll('.module-info-overlay').length === 0`));

  const d03f = await Eval(`(async () => {
    const btns = [...document.querySelectorAll('#lib-rows [data-info]')];
    btns[0].click();
    await new Promise((r) => setTimeout(r, 250));
    (btns[1] || btns[0]).click();
    await new Promise((r) => setTimeout(r, 250));
    return document.querySelectorAll('.module-info-overlay').length;
  })()`);
  check("重复打开 = 替换（无叠层残留）", d03f === 1, `overlay=${d03f}`);
  await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))`);
  await sleep(250);
} else {
  check("详情弹窗（库为空，跳过）", true);
}

// ================= 工单 04：悬空依赖警示 =================
const d04 = await Eval(`(() => {
  const dmap = window.__probe.mod.danglingDependencies(window.__probe.mods);
  const expectTags = window.__probe.mods.reduce((s, m) =>
    s + [...new Set(m.dependencies || [])].filter((d) => dmap[d]).length, 0);
  const seg = document.querySelector('#lib-stats .lib-dangling-count');
  return {
    expCount: Object.keys(dmap).length,
    statsHas: seg ? parseInt(seg.textContent.replace(/[^0-9]/g, ''), 10) : 0,
    tagCount: document.querySelectorAll('#lib-rows .dangling-tag').length,
    expectTags,
  };
})()`);
check("统计条悬空计数 = 纯函数期望（无悬空则不渲染红段）",
  d04.expCount === d04.statsHas, `expect=${d04.expCount} shown=${d04.statsHas}`);
check("行内 ⚠ 数 = 悬空依赖声明数（按重复声明去重）",
  d04.expectTags === d04.tagCount, `${d04.tagCount} vs ${d04.expectTags}`);
if (d04.expCount > 0) {
  const d04b = await Eval(`(() => {
    const tag = document.querySelector('#lib-rows .dangling-tag');
    const seg = document.querySelector('#lib-stats .lib-dangling-count');
    return { title: (tag && tag.getAttribute('title')) || '',
      color: tag ? getComputedStyle(tag).color : '',
      segColor: seg ? getComputedStyle(seg).color : '' };
  })()`);
  check("警示标 title = 缺失清单 + 引用方",
    d04b.title.includes("依赖未入库") && d04b.title.includes("引用"), d04b.title.slice(0, 60));
  check("警示标与统计条红段同色（danger 令牌，主题无关）",
    !!d04b.color && d04b.color === d04b.segColor, `${d04b.color} vs ${d04b.segColor}`);
} else {
  check("警示标 title 检查（库无悬空，跳过）", true);
  check("警示标同色检查（库无悬空，跳过）", true);
}

// ================= 工单 05：改简介模态（替代 window.prompt） =================
const e05slug = await Eval(`(document.querySelector('#lib-rows [data-edit-desc]') || {}).dataset?.editDesc || null`);
if (e05slug) {
  const expDesc = await expect(`String(mods.find((m) => m.slug === ${JSON.stringify(e05slug)}).description || '')`);
  await Eval(`document.querySelector('#lib-rows [data-edit-desc]').click()`);
  const e05 = await Eval(`(() => {
    const ov = document.querySelector('.lib-edit-overlay');
    if (!ov) return { count: 0 };
    return {
      count: document.querySelectorAll('.lib-edit-overlay').length,
      slug: (ov.querySelector('.lib-edit-slug') || {}).textContent || '',
      text: (ov.querySelector('.lib-edit-text') || {}).value ?? null,
      old: (ov.querySelector('.lib-edit-old') || {}).textContent || '',
      hasSave: !!ov.querySelector('.lib-edit-save'),
      hasCancel: !!ov.querySelector('.lib-edit-cancel'),
    };
  })()`);
  check("点「改简介」→ 模态出现（替换式唯一，非 window.prompt）",
    e05.count === 1, `overlay=${e05.count}`);
  check("模态：标题 slug + 文本域预填当前简介 + 原简介对照区",
    e05.slug === e05slug && e05.text === expDesc && e05.old === expDesc,
    `slug=${e05.slug} text=${String(e05.text).slice(0, 24)}`);
  check("保存 / 取消按钮齐备", e05.hasSave && e05.hasCancel);

  await Eval(`document.querySelector('.lib-edit-overlay .lib-edit-cancel').click()`);
  await c.waitFor(`!document.querySelector('.lib-edit-overlay')`, 4000);
  check("取消关闭（无残留）", await Eval(`document.querySelectorAll('.lib-edit-overlay').length === 0`));

  await Eval(`document.querySelector('#lib-rows [data-edit-desc]').click()`);
  await c.waitFor(`!!document.querySelector('.lib-edit-overlay')`, 5000);
  await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))`);
  await c.waitFor(`!document.querySelector('.lib-edit-overlay')`, 4000);
  check("Esc 关闭（无残留）", await Eval(`document.querySelectorAll('.lib-edit-overlay').length === 0`));

  await Eval(`document.querySelector('#lib-rows [data-edit-desc]').click()`);
  await c.waitFor(`!!document.querySelector('.lib-edit-overlay')`, 5000);
  await Eval(`document.querySelector('.lib-edit-overlay').dispatchEvent(new MouseEvent('click', { bubbles: true }))`);
  await c.waitFor(`!document.querySelector('.lib-edit-overlay')`, 4000);
  check("遮罩点击关闭（无残留）", await Eval(`document.querySelectorAll('.lib-edit-overlay').length === 0`));

  // 校验驳回态（确定性、零额度）：清空简介 → 保存 → 后端 400「缺少必填字段」
  // → 模态保持打开 + 错误就地展示。不触发 AI 一致性校验、不写库、不产生 git 提交。
  const e05e = await Eval(`(async () => {
    document.querySelector('#lib-rows [data-edit-desc]').click();
    await new Promise((r) => setTimeout(r, 250));
    const ov = document.querySelector('.lib-edit-overlay');
    ov.querySelector('.lib-edit-text').value = '';
    ov.querySelector('.lib-edit-save').click();
    for (let i = 0; i < 40; i++) {
      await new Promise((r) => setTimeout(r, 150));
      const cur = document.querySelector('.lib-edit-overlay');
      if (!cur) return { closed: true, msg: '' };
      const btn = cur.querySelector('.lib-edit-save');
      const msg = (cur.querySelector('.lib-edit-msg') || {}).textContent || '';
      if (msg) return { closed: false, msg, btnText: btn.textContent, btnEnabled: !btn.disabled };
    }
    return { closed: false, msg: 'TIMEOUT' };
  })()`);
  check("校验驳回：模态保持打开 + 后端中文错误 + 按钮复位可重试",
    !e05e.closed && e05e.msg !== 'TIMEOUT' && String(e05e.msg).includes("缺少必填字段：description")
      && e05e.btnText === "保存" && e05e.btnEnabled,
    e05e.msg || "(closed)");
  await Eval(`document.querySelector('.lib-edit-overlay .lib-edit-cancel')?.click()`);
  await sleep(200);
  check("驳回后取消可正常关闭（零写库零副作用）",
    await Eval(`document.querySelectorAll('.lib-edit-overlay').length === 0`));
} else {
  check("改简介模态（库为空，跳过）", true);
}

// ================= 工单 06：编辑弹窗（身份 + 平台文件） =================
const emSlug = await Eval(`(document.querySelector('#lib-rows [data-edit-mod]') || {}).dataset?.editMod || null`);
if (emSlug) {
  const emExp = await expect(`(() => {
    const m = mods.find((x) => x.slug === ${JSON.stringify(emSlug)});
    const names = Object.keys(m.platforms || {});
    const entry = (m.platforms || {})[names[0]] || {};
    return { names, kit: entry.kit || '', url: entry.source_url || '',
      files: (entry.files || []).length, kits: [...new Set(mods.flatMap((x) =>
        Object.values(x.platforms || {}).map((p) => p.kit).filter(Boolean)))].length };
  })()`);
  await Eval(`document.querySelector('#lib-rows [data-edit-mod]').click()`);
  await c.waitFor(`!!document.querySelector('.lib-edit-overlay .lib-mod-platform')`, 5000);
  const f06 = await Eval(`(() => {
    const ov = document.querySelector('.lib-edit-overlay');
    return {
      optVals: [...ov.querySelectorAll('.lib-mod-platform option')].map((o) => o.value),
      kit: ov.querySelector('.lib-mod-kit').value,
      url: ov.querySelector('.lib-mod-url').value,
      lis: ov.querySelectorAll('.lib-mod-files li').length,
      embedded: !!ov.querySelector('.lib-mod-files li.muted'),
      kitOptions: ov.querySelectorAll('#lib-mod-kit-list option').length,
      statusText: ov.querySelector('.lib-mod-status').textContent,
      hasSave: !!ov.querySelector('.lib-mod-save'),
      hasAddRow: !!ov.querySelector('.lib-mod-addrow'),
      hasPick: !!ov.querySelector('.lib-mod-pick'),
    };
  })()`);
  check("「编辑」→ 模态出现，平台下拉 = 该模块平台版本清单",
    JSON.stringify(f06.optVals) === JSON.stringify(emExp.names), f06.optVals.join(","));
  check("套件 / 购买链接预填 = 当前平台条目值", f06.kit === emExp.kit && f06.url === emExp.url,
    `kit=${f06.kit} url=${String(f06.url).slice(0, 30)}`);
  check("平台文件清单行数 = 条目文件数（无文件 = 内嵌母版态）",
    f06.lis === (emExp.files || 1) && f06.embedded === (emExp.files === 0),
    `lis=${f06.lis} exp=${emExp.files} embedded=${f06.embedded}`);
  check("kit 词表提示（datalist 选项 = 库内 kit 去重数）", f06.kitOptions === emExp.kits,
    `${f06.kitOptions} vs ${emExp.kits}`);
  check("只读状态行（验证状态 / 硬件绑定 / 指向其它入口）",
    f06.statusText.includes("验证状态") && f06.statusText.includes("硬件绑定"), f06.statusText.slice(0, 40));
  check("新增文件入口齐备（+ 文件 / 选择文件… / 保存）",
    f06.hasSave && f06.hasAddRow && f06.hasPick);

  // 前端 URL 校验：非法值 → 提示且不发请求
  const f06b = await Eval(`(async () => {
    const ov = document.querySelector('.lib-edit-overlay');
    const urlEl = ov.querySelector('.lib-mod-url');
    const keep = urlEl.value;
    urlEl.value = 'not-a-url';
    ov.querySelector('.lib-mod-save').click();
    await new Promise((r) => setTimeout(r, 200));
    const msg = ov.querySelector('.lib-mod-msg').textContent;
    urlEl.value = keep;
    return { msg };
  })()`);
  check("非法 URL → 前端拦截提示（不发请求、不写库）",
    f06b.msg.includes("购买链接格式不正确"), f06b.msg);
  await Eval(`document.querySelector('.lib-edit-overlay .lib-mod-cancel').click()`);
  await c.waitFor(`!document.querySelector('.lib-edit-overlay')`, 4000);

  // 后端失败路径：内存假模块（不在库里）→ platform-identity 404 → 表单保留 + 错误展示。
  // 渲染入口 renderLibraryTable 是模块作用域，脚本改用 ui/library.js 的导出 editModule 打开弹窗。
  const f06c = await Eval(`(async () => {
    const P = window.__probe;
    const fake = { slug: 'probe_edit', description: 'probe', dependencies: [], platforms: {
      stm32: { files: ['p.c'], verified: false, hardware_bound: false, kit: '', source_url: '' } } };
    P.app.state.modules = [...(P.app.state.modules || []), fake];
    P.ui.lib.editModule('probe_edit');
    await new Promise((r) => setTimeout(r, 300));
    let ov = document.querySelector('.lib-edit-overlay');
    if (!ov) return { opened: false };
    ov.querySelector('.lib-mod-url').value = 'https://example.com/buy';
    ov.querySelector('.lib-mod-save').click();
    let msg = '';
    for (let i = 0; i < 40; i++) {
      await new Promise((r) => setTimeout(r, 150));
      msg = (document.querySelector('.lib-edit-overlay .lib-mod-msg') || {}).textContent || '';
      if (msg) break;
    }
    ov = document.querySelector('.lib-edit-overlay');
    const out = { opened: true, msg, gone: !ov,
      btnEnabled: !!ov && !ov.querySelector('.lib-mod-save').disabled };
    if (ov) ov.querySelector('.lib-mod-cancel').click();
    P.app.state.modules = P.app.state.modules.filter((m) => m.slug !== 'probe_edit');
    return out;
  })()`);
  check("假模块保存身份 → 后端错误展示（404 路径，表单保留可重试）",
    f06c.opened && !f06c.gone && !!f06c.msg && f06c.msg !== 'TIMEOUT' && f06c.btnEnabled,
    String(f06c.msg).slice(0, 60));
  check("关闭后无弹窗残留 + 内存假模块已移除（真实库零改动）",
    await Eval(`document.querySelectorAll('.lib-edit-overlay').length === 0
      && !window.__probe.app.state.modules.some((m) => m.slug === 'probe_edit')`));
} else {
  check("编辑弹窗（库为空，跳过）", true);
}

// ================= 工单 07：添加模块表单分区折叠 =================
// 口径修订（commit 4dcfa75b「工单 07 评审整改」）：③ 进阶区**默认展开**
// （入库按钮常驻可见，与参考侧对齐），故此处断言 ①③ 展开、② 折叠。
const g07 = await Eval(`(() => {
  const secs = ["basic", "files", "adv"].map((k) => document.getElementById("add-sec-" + k));
  const heads = secs.map((s) => s && s.querySelector(".add-section-head"));
  if (!secs.every(Boolean) || !heads.every(Boolean)) return { hasSecs: false };
  const ids = ["new-slug","new-platform","new-desc","new-deps","new-hw","new-verified",
    "new-notes","new-files","btn-add-file-row","btn-pick-mod-files","btn-pick-mod-dir",
    "btn-draft-desc","btn-add-module-submit","add-msg"].map((i) => !!document.getElementById(i));
  return {
    hasSecs: true, aria: heads.map((h) => h.getAttribute("aria-expanded")).join(","),
    basicCollapsed: secs[0].classList.contains("collapsed"),
    filesCollapsed: secs[1].classList.contains("collapsed"),
    advCollapsed: secs[2].classList.contains("collapsed"),
    idsAll: ids.every(Boolean),
    draftInBasic: document.getElementById('btn-draft-desc').closest('.add-section').id === 'add-sec-basic',
    draftSameSectionAsDesc: document.getElementById('btn-draft-desc').closest('.add-section')
      === document.getElementById('new-desc').closest('.add-section')
      && document.getElementById('btn-draft-desc').closest('.add-section')
      === document.getElementById('new-desc-msg').closest('.add-section'),
    draftVisible: document.getElementById('btn-draft-desc').offsetParent !== null,
    submitVisible: document.getElementById('btn-add-module-submit').offsetParent !== null,
  };
})()`);
check("三分区存在 + 分区头齐备", g07.hasSecs);
check("默认态：① 展开、② 折叠、③ 展开（评审整改：入库按钮常驻可见）",
  !g07.basicCollapsed && g07.filesCollapsed && !g07.advCollapsed,
  `basic=${g07.basicCollapsed} files=${g07.filesCollapsed} adv=${g07.advCollapsed}`);
check("aria-expanded 与实际折叠态一致 + 提交按钮可见",
  g07.aria === "true,false,true" && g07.submitVisible, `aria=${g07.aria}`);
check("全部字段 id / 提交按钮仍在（零改动校验）", g07.idsAll);
// 口径修订（commit 70a0c3e3「工单 07 录入/编辑绕路」）：AI 草稿按钮**与简介输入框同线**
// （① 基本信息区），草稿反馈槽 #new-desc-msg 就近同区——不再落在 ③ 进阶区。
check("「AI 出简介草稿」与简介输入框 / 反馈槽同区（①基本信息）且可见",
  g07.draftInBasic && g07.draftSameSectionAsDesc && g07.draftVisible,
  `basic=${g07.draftInBasic} same=${g07.draftSameSectionAsDesc} visible=${g07.draftVisible}`);

const g07b = await Eval(`(async () => {
  const slug = document.getElementById('new-slug');
  slug.value = 'probe_collapse';
  const head0 = document.querySelector('#add-sec-basic .add-section-head');
  head0.click();
  await new Promise((r) => setTimeout(r, 100));
  const basic1 = document.getElementById('add-sec-basic').classList.contains('collapsed');
  head0.click();
  await new Promise((r) => setTimeout(r, 100));
  const basic2 = document.getElementById('add-sec-basic').classList.contains('collapsed');
  const slugBack = document.getElementById('new-slug').value;
  const fileRows = document.querySelectorAll('#new-files .file-row').length;
  const head1 = document.querySelector('#add-sec-files .add-section-head');
  head1.click();
  await new Promise((r) => setTimeout(r, 100));
  const files1 = document.getElementById('add-sec-files').classList.contains('collapsed');
  head1.click();
  await new Promise((r) => setTimeout(r, 100));
  const fileRows2 = document.querySelectorAll('#new-files .file-row').length;
  slug.value = '';
  return { basic1, basic2, slugBack, fileRows, files1, fileRows2 };
})()`);
check("① 收起后可再展开，已填 slug 保留",
  g07b.basic1 && !g07b.basic2 && g07b.slugBack === "probe_collapse");
check("② 折叠往返后文件行保留（display:none 不销毁）",
  g07b.files1 === false && g07b.fileRows2 === g07b.fileRows, `${g07b.fileRows2} vs ${g07b.fileRows}`);

// ================= 工单 01：视觉令牌化细目（把「目视验收」落成机器判据） =================
// 口径：工单 01 的验收原本含「人工目视」，本轮把它拆成可机器判定的等价判据
// （同源样式 / CSSOM 令牌规则 / 跨表作用域），截图仅作存档。

// ① 行 hover 沿用全局规则、无斑马纹（斑马纹已由「相邻行背景一致且透明」断言）
const token01 = await Eval(`(() => {
  let hoverRule = '', zebra = '';
  for (const ss of document.styleSheets) {
    let rules; try { rules = ss.cssRules; } catch (e) { continue; }
    for (const r of rules) {
      const sel = r.selectorText || '';
      if (sel.includes('tbody tr:hover')) hoverRule = sel + ' { ' + r.style.cssText.slice(0, 120) + ' }';
      if (/nth-child\\(\\s*(odd|even)\\s*\\)/.test(sel) && sel.includes('lib-table')) zebra = sel;
    }
  }
  return { hoverRule, zebra };
})()`);
check("行 hover 沿用全局 tbody tr:hover（未新造令牌）；.lib-table 无斑马纹规则",
  token01.hoverRule.includes("tbody tr:hover") && token01.zebra === "", token01.hoverRule || "无 hover 规则");

// ② 平台徽章 = moduleBadges 同源渲染（DOM 徽章列与纯件输出逐字节一致）
const badgeSame = await Eval(`(() => {
  const tr = [...document.querySelectorAll('#lib-rows tr')].find((r) => {
    const slug = r.querySelector('td.slug')?.textContent.trim();
    return window.__probe.mods.some((m) => m.slug === slug);
  });
  if (!tr) return { ok: false };
  const tds = [...tr.querySelectorAll('td')];
  const slug = tds[0].textContent.trim();
  const mod = window.__probe.mods.find((m) => m.slug === slug);
  return { ok: true, slug, dom: tds[3].innerHTML, exp: window.__probe.mod.moduleBadges(mod),
    platBadges: tds[3].querySelectorAll('.badge.plat').length,
    embedded: tds[3].querySelectorAll('.badge:not(.plat)').length };
})()`);
check("平台徽章列 = moduleBadges 纯件同源输出（同源样式 = 同配色）",
  badgeSame.ok && badgeSame.dom === badgeSame.exp && badgeSame.platBadges > 0,
  `${badgeSame.slug}: plat=${badgeSame.platBadges} 内嵌=${badgeSame.embedded}`);

// ③ 操作列按钮：同行四钮几何完全统一（同一套表格钮样式），danger 只是颜色不同
//（红色警示）——「统一」的机器判据 = 几何逐项相等 + 颜色唯 danger 不同。
const token03 = await Eval(`(() => {
  const geo = (b) => { const cs = getComputedStyle(b);
    return { fontSize: cs.fontSize, padding: cs.padding, borderRadius: cs.borderRadius,
      borderWidth: cs.borderWidth, borderColor: cs.borderColor, color: cs.color,
      bg: cs.backgroundColor, fontWeight: cs.fontWeight }; };
  const btns = [...document.querySelectorAll('#lib-rows tr:first-child button')];
  return { n: btns.length, styles: btns.map(geo),
    dangerIdx: btns.findIndex((b) => b.classList.contains('danger')),
    plain: geo(document.querySelector('#lib-rows [data-info]')) };
})()`);
const geoKey = (s) => [s.fontSize, s.padding, s.borderRadius, s.borderWidth, s.borderColor,
  s.bg, s.fontWeight].join("|");
check("操作列四钮样式统一（几何 / 底色 / 字重逐项一致）",
  token03.n === 4 && token03.styles.every((s) => geoKey(s) === geoKey(token03.plain)),
  `n=${token03.n} 首个=${geoKey(token03.plain)}`);
check("删除钮保 danger 红色警示（唯一颜色差异 = 前景红）",
  token03.dangerIdx === 3
    && token03.styles[3].color !== token03.plain.color
    && token03.styles.slice(0, 3).every((s) => s.color === token03.plain.color),
  `${token03.styles[3] && token03.styles[3].color} vs ${token03.plain.color}`);

// ④ slug 首列等宽（限 .lib-table 作用域）——跨表佐证放到 07 段之后（需切 tab）
check("slug 列等宽、简介列非等宽（作用域限 td.slug）", await Eval(`(() => {
  const slug = document.querySelector('#lib-rows td.slug');
  const desc = document.querySelector('#lib-rows td.desc-cell');
  return getComputedStyle(slug).fontFamily.includes('mono')
    && !getComputedStyle(desc).fontFamily.includes('mono');
})()`));

// ⑤ 加载态占位 + 错误态容器走全局 .error（重拉一次模块库，捕获加载中那一帧）
const token05 = await Eval(`(async () => {
  const lib = window.__probe.ui.lib;
  const p = lib.loadLibrary();          // 占位是同步写入的，先抓再 await
  const html = document.getElementById('lib-rows').innerHTML;
  await p;
  return { html, msgClass: document.getElementById('lib-msg').className,
    esTitle: /class="es-title"/.test(html), icon: html.includes('⏳') };
})()`);
await c.waitFor(`document.querySelectorAll('#lib-rows tr').length === ${modTotal}`, 15000);
check("加载态：⏳ + es-title「正在读取模块库…」占位（同全站空态结构）",
  token05.icon && token05.esTitle, token05.html.includes("正在读取模块库…") ? "文案在场" : "文案缺失");
check("错误态容器走全局 .error（#lib-msg）", token05.msgClass.includes("error"), token05.msgClass);

// ⑥ 跨表作用域：参考文件库 / 母版库不受「.lib-table td.slug 等宽」波及，且
//    参考库表格按钮与模块库同套表格钮样式（对偶表视觉统一）
const crossTable = await Eval(`(async () => {
  const click = (tab) => { const b = [...document.querySelectorAll('nav button')].find((x) => x.dataset.tab === tab); if (b) b.click(); };
  const geoKey = (b) => { const cs = getComputedStyle(b);
    return [cs.fontSize, cs.padding, cs.borderRadius, cs.borderWidth, cs.backgroundColor].join('|'); };
  const out = { libBtn: geoKey(document.querySelector('#lib-rows [data-info]')) };
  click('reference');
  // 等真实行（占位行也有 td，判据必须用行内按钮）
  for (let i = 0; i < 80 && !document.querySelector('#ref-rows [data-ref-view]'); i++) await new Promise((r) => setTimeout(r, 200));
  const refTd = document.querySelector('#ref-rows td');
  out.refSlugClass = document.querySelectorAll('#ref-rows td.slug').length;
  out.refMono = refTd ? getComputedStyle(refTd).fontFamily.includes('mono') : null;
  out.refIsLibTable = !!document.querySelector('#tab-reference table.lib-table');
  out.refBtn = document.querySelector('#ref-rows [data-ref-view]') ? geoKey(document.querySelector('#ref-rows [data-ref-view]')) : null;
  click('master');
  for (let i = 0; i < 60 && !document.querySelector('#master-rows td'); i++) await new Promise((r) => setTimeout(r, 200));
  out.masterSlugClass = document.querySelectorAll('#master-rows td.slug').length;
  out.masterIsLibTable = !!document.querySelector('#master-rows').closest('table').classList.contains('lib-table');
  const mSlug = document.querySelector('#master-rows td.slug');
  out.masterMono = mSlug ? getComputedStyle(mSlug).fontFamily.includes('mono') : null;
  click('library');
  for (let i = 0; i < 60 && document.querySelectorAll('#lib-rows tr').length !== ${modTotal}; i++) await new Promise((r) => setTimeout(r, 200));
  out.backRows = document.querySelectorAll('#lib-rows tr').length;
  return out;
})()`);
check("等宽作用域不波及参考库（无 td.slug，标题列非等宽）",
  crossTable.refSlugClass === 0 && crossTable.refMono === false && crossTable.refIsLibTable,
  `slug=${crossTable.refSlugClass} mono=${crossTable.refMono}`);
// 母版表本身就用 td.slug 放平台名（fx/master.js）——作用域靠 .lib-table 前缀生效：
// 母版表无 .lib-table 类 → 等宽规则不命中（实测 mono=false）
check("等宽作用域不波及母版库（表无 .lib-table，其 td.slug 非等宽）",
  crossTable.masterIsLibTable === false && crossTable.masterSlugClass > 0
    && crossTable.masterMono === false,
  `lib-table=${crossTable.masterIsLibTable} slug=${crossTable.masterSlugClass} mono=${crossTable.masterMono}`);
check("参考库表格按钮与模块库同套表格钮样式（对偶表视觉统一）",
  crossTable.refBtn !== null && crossTable.refBtn === crossTable.libBtn,
  `${crossTable.refBtn} vs ${crossTable.libBtn}`);
check("跨表切换后模块库回到全量（状态无污染）", crossTable.backRows === modTotal,
  `${crossTable.backRows} vs ${modTotal}`);

// ================= 截图存档（工单 01 目视验收产物） =================
// 取景（第十轮目视验收修）：此前直接 `#tab-library.scrollIntoView({block:'start'})`
// 截图 —— 页面 scrollTop 落在 68，而 header 是 `position:sticky; top:0`（高 48px），
// 于是标题 h2 被吸顶栏盖掉一半，第一眼像渲染故障。改为**滚回页顶**再截，
// 不隐藏任何 chrome（保持截图 = 用户真实所见）。
const shotPath = (name) => join(ROOT, ".scratch", "module-library-ui", name);
const shoot = async (name) => {
  await Eval(`window.scrollTo(0, 0)`);
  await sleep(400);
  const shot = await c.cdp("Page.captureScreenshot", { format: "png" });
  mkdirSync(join(ROOT, ".scratch", "module-library-ui"), { recursive: true });
  writeFileSync(shotPath(name), Buffer.from(shot.result.data, "base64"));
  console.log(name + " 已存档");
};
await Eval(`document.getElementById('lib-filter-clear').click()`);
await c.waitFor(`document.querySelectorAll('#lib-rows tr').length === ${modTotal}`, 8000);
await shoot("01-table-shot.png");

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");

// 脏标签退出保护（beforeunload）会拦 reload —— 先重载出干净页再收尾截图
await c.cdp("Page.navigate", { url: PAGE_URL });
await c.waitFor(`document.readyState === 'complete' && !!document.getElementById('tab-library')`, 20000);
await Eval(`(() => { const b = [...document.querySelectorAll('nav button')].find((x) => x.dataset.tab === 'library'); if (b) b.click(); return true; })()`);
await c.waitFor(`document.querySelectorAll('#lib-rows tr').length > 1`, 20000);
await shoot("01-table-shot-final.png");
c.close();
process.exit(failed === 0 ? 0 : 1);
