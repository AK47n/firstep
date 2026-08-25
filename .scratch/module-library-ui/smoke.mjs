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

// ---- 工单 02：工具栏与统计条（搜索 / 过滤 / 排序 / 统计，全部客户端） ----
const hasToolbar = await Eval(`!!(document.getElementById('lib-search')
  && document.getElementById('lib-sort')
  && document.getElementById('lib-filter-clear')
  && document.getElementById('lib-stats')
  && document.getElementById('lib-platform-chips')
  && document.getElementById('lib-status-chips'))`);
check("工具栏元素齐全（搜索 / 排序 / 清空 / 统计 / 两组 chips）", hasToolbar);

const nonEmpty = await Eval(`(state.modules || []).length > 0`);

const t02 = await Eval(`(() => {
  const statsText = document.getElementById('lib-stats').textContent;
  const platVals = [...document.querySelectorAll('#lib-platform-chips .lib-chip')].map((b) => b.getAttribute('data-lib-chip'));
  const statusVals = [...document.querySelectorAll('#lib-status-chips .lib-chip')].map((b) => b.getAttribute('data-lib-chip'));
  const expectedPlats = Object.keys(libStats(state.modules || []).platforms);
  const rowSlugs = [...document.querySelectorAll('#lib-rows td.slug')].map((td) => td.textContent);
  return {
    statsText, platVals, statusVals, expectedPlats, rowSlugs,
    total: (state.modules || []).length,
  };
})()`);
check("统计条以「共 N 个模块」开头（N=全量模块数）",
  t02.statsText.startsWith("共 " + t02.total + " 个模块"), t02.statsText);
check("平台 chips = 全部 + 库内平台（含计数）",
  t02.platVals[0] === "" && t02.expectedPlats.every((p) => t02.platVals.includes(p)),
  t02.platVals.join(","));
check("状态 chips = 全部 / 已验证 / 未验证 / 硬件绑定",
  t02.statusVals.join(",") === ",verified,unverified,hardware_bound", t02.statusVals.join(","));
check("无过滤时行数 = 模块数", t02.rowSlugs.length === t02.total, `${t02.rowSlugs.length} vs ${t02.total}`);

if (nonEmpty) {
  // 搜索过滤：输入无关词 → 空结果态；输入真实 slug 子串 → 命中；清空 → 恢复全量
  const search = await Eval(`(async () => {
    const input = document.getElementById('lib-search');
    const slug0 = (state.modules || [])[0].slug;
    input.value = 'zzz无关词zzz';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise((r) => setTimeout(r, 250));
    const emptyRows = document.querySelectorAll('#lib-rows tr').length;
    const emptyTitle = (document.querySelector('#lib-rows .es-title') || {}).textContent || '';
    input.value = slug0.slice(0, Math.min(4, slug0.length)).toUpperCase();
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise((r) => setTimeout(r, 250));
    const hitSlugs = [...document.querySelectorAll('#lib-rows td.slug')].map((td) => td.textContent);
    document.getElementById('lib-filter-clear').click();
    await new Promise((r) => setTimeout(r, 250));
    const backRows = document.querySelectorAll('#lib-rows tr').length;
    return { emptyRows, emptyTitle, hitSlugs, backRows, total: (state.modules || []).length, slug0 };
  })()`);
  check("无关词 → 空结果态（友好提示 + 仅 1 行占位）",
    search.emptyRows === 1 && search.emptyTitle.includes("没有匹配的模块"), search.emptyTitle);
  // q 匹配多字段（其他模块可能因 kit/notes 含关键词命中）：只断言输入 slug 自身必命中
  check("真实 slug（大写输入）命中且大小写不敏感",
    search.hitSlugs.includes(search.slug0), search.hitSlugs.join(","));
  check("清空按钮恢复全量行数", search.backRows === search.total, `${search.backRows} vs ${search.total}`);

  // chips 点击过滤 + 再点一次取消 + Esc 全清
  const chips = await Eval(`(async () => {
    const plat = document.querySelector('#lib-platform-chips .lib-chip[data-lib-chip]:not([data-lib-chip=""])');
    if (!plat) return { skipped: true };
    const pv = plat.getAttribute('data-lib-chip');
    const expected = libFilterModules(state.modules, { q: '', platform: pv, status: '' }).length;
    plat.click();
    await new Promise((r) => setTimeout(r, 250));
    const filteredRows = document.querySelectorAll('#lib-rows tr').length;
    const onCount = document.querySelectorAll('#lib-platform-chips .lib-chip.on').length;
    // 再点一次：chips 已重渲染，重新查询当前选中项再点击（detached 旧元素点击无效）
    const onPlat = document.querySelector('#lib-platform-chips .lib-chip.on');
    if (onPlat) onPlat.click();
    await new Promise((r) => setTimeout(r, 250));
    const clearedRows = document.querySelectorAll('#lib-rows tr').length;
    const input = document.getElementById('lib-search');
    input.value = 'zzz无关词zzz';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await new Promise((r) => setTimeout(r, 250));
    const escRows = document.querySelectorAll('#lib-rows tr').length;
    return { skipped: false, expected, filteredRows, onCount, clearedRows, escRows, total: (state.modules || []).length };
  })()`);
  if (!chips.skipped) {
    check("平台 chip 点击过滤（行数 = 纯函数期望值，且选中态高亮）",
      chips.filteredRows === chips.expected && chips.onCount === 1, `${chips.filteredRows} vs ${chips.expected}`);
    check("再点一次取消过滤 → 恢复全量", chips.clearedRows === chips.total);
    check("Esc 清空搜索 → 恢复全量", chips.escRows === chips.total, `${chips.escRows} vs ${chips.total}`);
  } else {
    check("平台 chip 过滤（无平台数据，跳过）", true);
  }

  // 排序：按平台数降序 → 全行序列 = 纯函数同参数全序列（首位相同也不放侥幸）
  const sort = await Eval(`(async () => {
    const sel = document.getElementById('lib-sort');
    sel.value = 'platforms';
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    document.getElementById('lib-sort-dir').click();
    await new Promise((r) => setTimeout(r, 250));
    const rowsNow = [...document.querySelectorAll('#lib-rows td.slug')].map((td) => td.textContent);
    const expectedSeq = libSortModules(state.modules, { by: 'platforms', dir: 'desc' }).map((m) => m.slug);
    const dirBtn = document.getElementById('lib-sort-dir').textContent;
    document.getElementById('lib-sort-dir').click();
    return { seqMatch: JSON.stringify(rowsNow) === JSON.stringify(expectedSeq), rowsNow, expectedSeq, dirBtn };
  })()`);
  check("排序（平台数降序）行序列与纯函数完全一致",
    sort.seqMatch, `first=${sort.rowsNow[0]} exp=${sort.expectedSeq[0]}`);
}

// ---- 工单 03：行「详情」→ 全量信息弹窗（无平台上下文） ----
const d03 = await Eval(`(() => {
  const infoBtn = document.querySelector('#lib-rows [data-info]');
  if (!infoBtn) return { skipped: true };
  const slug = infoBtn.getAttribute('data-info');
  const mod = (state.modules || []).find((m) => m.slug === slug) || {};
  const platCount = Object.keys(mod.platforms || {}).length;
  infoBtn.click();
  return { skipped: false, slug, platCount };
})()`);
if (!d03.skipped) {
  const d03b = await Eval(`(() => {
    const overlay = document.querySelector('.module-info-overlay');
    const overlayCount = document.querySelectorAll('.module-info-overlay').length;
    const title = overlay ? (overlay.querySelector('.module-info-title .slug') || {}).textContent || '' : '';
    const plats = overlay ? overlay.querySelectorAll('.module-info-platforms .mi-plat').length : 0;
    const offText = overlay ? overlay.querySelector('.module-info-off') : null;
    const files = overlay ? overlay.querySelectorAll('.mi-files li').length : 0;
    return { overlayCount, title, plats, offText: !!offText, files };
  })()`);
  check("点「详情」→ 弹窗出现（唯一）", d03b.overlayCount === 1, `overlay=${d03b.overlayCount}`);
  check("弹窗标题 = 该行 slug", d03b.title === d03.slug, `${d03b.title} vs ${d03.slug}`);
  check("全部平台分段展示（无 off 提示）", d03b.plats === d03.platCount && !d03b.offText,
    `plats=${d03b.plats}/${d03.platCount}`);
  // Esc 关闭 → 无残留
  await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))`);
  await new Promise((r) => setTimeout(r, 250));
  const d03c = await Eval(`document.querySelectorAll('.module-info-overlay').length`);
  check("Esc 关闭弹窗（无残留）", d03c === 0, `overlay=${d03c}`);
  // 再开弹窗 → 遮罩点击关闭
  await Eval(`document.querySelector('#lib-rows [data-info]').click()`);
  await new Promise((r) => setTimeout(r, 250));
  const d03d = await Eval(`(() => {
    const overlay = document.querySelector('.module-info-overlay');
    if (!overlay) return { mask: false };
    overlay.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    return { mask: true };
  })()`);
  await new Promise((r) => setTimeout(r, 250));
  const d03e = await Eval(`document.querySelectorAll('.module-info-overlay').length`);
  check("遮罩点击关闭弹窗", d03d.mask && d03e === 0, `overlay=${d03e}`);
  // ✕ 按钮关闭
  await Eval(`document.querySelector('#lib-rows [data-info]').click()`);
  await new Promise((r) => setTimeout(r, 250));
  const d03g = await Eval(`(() => {
    const overlay = document.querySelector('.module-info-overlay');
    const closeBtn = overlay && overlay.querySelector('.ref-files-close');
    if (!closeBtn) return { x: false };
    closeBtn.click();
    return { x: true };
  })()`);
  await new Promise((r) => setTimeout(r, 250));
  const d03h = await Eval(`document.querySelectorAll('.module-info-overlay').length`);
  check("✕ 按钮关闭弹窗", d03g.x && d03h === 0, `overlay=${d03h}`);
  // 重复打开 = 替换（先开一个再点另一行详情，仍只有一个 overlay）
  const d03f = await Eval(`(async () => {
    const btns = [...document.querySelectorAll('#lib-rows [data-info]')];
    btns[0].click();
    await new Promise((r) => setTimeout(r, 250));
    btns[1].click();
    await new Promise((r) => setTimeout(r, 250));
    const count = document.querySelectorAll('.module-info-overlay').length;
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    return { count };
  })()`);
  check("重复打开 = 替换（无叠层残留）", d03f.count === 1, `overlay=${d03f.count}`);
} else {
  check("详情弹窗（无模块数据，跳过）", true);
}

// ---- 工单 04：悬空依赖警示（行内 ⚠ + 统计条红色计数） ----
const d04 = await Eval(`(() => {
  const dmap = typeof danglingDependencies === 'function' ? danglingDependencies(state.modules || []) : null;
  const expectCount = dmap ? Object.keys(dmap).length : -1;
  const statsSpan = document.querySelector('#lib-stats .lib-dangling-count');
  const statsHas = statsSpan ? parseInt(statsSpan.textContent.replace(/[^0-9]/g, ''), 10) : 0;
  const tagCount = document.querySelectorAll('#lib-rows .dangling-tag').length;
  const expectTags = dmap ? (state.modules || []).reduce((s, m) =>
    s + [...new Set(m.dependencies || [])].filter((d) => dmap[d]).length, 0) : -1;
  return { expectCount, statsHas, tagCount, expectTags };
})()`);
check("统计条悬空计数 = 纯函数期望（无悬空时不显示红段）",
  d04.expectCount === d04.statsHas,
  `expect=${d04.expectCount} shown=${d04.statsHas}`);
check("行内 ⚠ 警示标数量 = 悬空依赖声明数",
  d04.expectTags === d04.tagCount, `${d04.tagCount} vs ${d04.expectTags}`);
// 有悬空时：警示标 title 含「依赖未入库」与引用方；颜色与统计条红段一致（主题无关）
if (d04.expectCount > 0) {
  const d04b = await Eval(`(() => {
    const tag = document.querySelector('#lib-rows .dangling-tag');
    const countSpan = document.querySelector('#lib-stats .lib-dangling-count');
    return {
      title: (tag && tag.getAttribute('title')) || '',
      color: tag ? getComputedStyle(tag).color : '',
      countColor: countSpan ? getComputedStyle(countSpan).color : '',
    };
  })()`);
  check("警示标 title = 缺失清单 + 引用方",
    d04b.title.includes("依赖未入库") && d04b.title.includes("引用"), d04b.title);
  // 不比对具体 rgb（--danger 随主题变）：只需两者同为 danger 令牌色
  check("警示标与统计条红段同色（danger 令牌，主题无关）",
    !!d04b.color && d04b.color === d04b.countColor, `${d04b.color} vs ${d04b.countColor}`);
} else {
  check("警示标 title/红色检查（库无悬空，跳过）", true);
}
// 修好即消失：给悬空依赖「补库」后（纯前端重算）统计条消失——用已入库模块验证：
// 实际写入入库需后端，这里验证渲染一致性：dmap 空 → 无 span 且无 tag
const d04c = await Eval(`(() => {
  const dmap = danglingDependencies(state.modules || []);
  return Object.keys(dmap).length === 0
    ? { noSpan: !document.querySelector('#lib-stats .lib-dangling-count'),
        noTags: document.querySelectorAll('#lib-rows .dangling-tag').length === 0 }
    : { noSpan: true, noTags: true, skipped: true };
})()`);
if (!d04c.skipped) {
  check("无悬空时统计条无红段且行内无 ⚠", d04c.noSpan && d04c.noTags);
} else {
  check("无悬空一致性（库有悬空，跳过）", true);
}

// ---- 工单 05：改简介模态（替代 window.prompt，三态反馈） ----
const e05 = await Eval(`(() => {
  const btn = document.querySelector('#lib-rows [data-edit-desc]');
  if (!btn) return { skipped: true };
  const slug = btn.getAttribute('data-edit-desc');
  const mod = (state.modules || []).find((m) => m.slug === slug) || {};
  const desc = String(mod.description || '');
  btn.click();
  return { skipped: false, slug, desc, overlayCount: document.querySelectorAll('.lib-edit-overlay').length };
})()`);
if (!e05.skipped) {
  const e05b = await Eval(`(() => {
    const overlay = document.querySelector('.lib-edit-overlay');
    const textEl = overlay && overlay.querySelector('.lib-edit-text');
    const oldEl = overlay && overlay.querySelector('.lib-edit-old');
    const slugEl = overlay && overlay.querySelector('.lib-edit-slug');
    const hasSave = overlay && !!overlay.querySelector('.lib-edit-save');
    const hasCancel = overlay && !!overlay.querySelector('.lib-edit-cancel');
    return { text: textEl ? textEl.value : null, old: oldEl ? oldEl.textContent : null,
             slug: slugEl ? slugEl.textContent : null, hasSave, hasCancel };
  })()`);
  check("点「改简介」→ 模态出现（替换式唯一）", e05.overlayCount === 1, `overlay=${e05.overlayCount}`);
  check("模态标题 slug + 文本域预填当前简介 + 原简介对照区",
    e05b.slug === e05.slug && e05b.text === e05.desc && e05b.old === e05.desc,
    `slug=${e05b.slug} text=${e05b.text} old=${e05b.old}`);
  check("保存 / 取消按钮齐备", e05b.hasSave && e05b.hasCancel);
  // 取消关闭
  await Eval(`document.querySelector('.lib-edit-overlay .lib-edit-cancel').click()`);
  await new Promise((r) => setTimeout(r, 250));
  const e05c = await Eval(`document.querySelectorAll('.lib-edit-overlay').length`);
  check("取消关闭（无残留）", e05c === 0, `overlay=${e05c}`);
  // Esc 关闭
  await Eval(`document.querySelector('#lib-rows [data-edit-desc]').click()`);
  await new Promise((r) => setTimeout(r, 250));
  await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))`);
  await new Promise((r) => setTimeout(r, 250));
  const e05d = await Eval(`document.querySelectorAll('.lib-edit-overlay').length`);
  check("Esc 关闭（无残留）", e05d === 0, `overlay=${e05d}`);
  // 真实保存（原文不动）：成功（AI 校验一致）→ 模态关闭；驳回（未配置/不一致）→ 错误展示。
  // 二态任一均符合「三态反馈」验收；轮询至多 8s。
  const e05e = await Eval(`(async () => {
    document.querySelector('#lib-rows [data-edit-desc]').click();
    await new Promise((r) => setTimeout(r, 250));
    document.querySelector('.lib-edit-overlay .lib-edit-save').click();
    for (let i = 0; i < 40; i++) {
      await new Promise((r) => setTimeout(r, 200));
      const gone = document.querySelectorAll('.lib-edit-overlay').length === 0;
      const msg = (document.querySelector('.lib-edit-overlay .lib-edit-msg') || {}).textContent || '';
      if (gone) return { closed: true, msg };
      if (msg) return { closed: false, msg };
    }
    return { closed: false, msg: 'TIMEOUT' };
  })()`);
  check("保存 = 成功关闭或驳回展示（两种状态流转均成立）",
    (e05e.closed && !e05e.msg) || (!e05e.closed && e05e.msg && e05e.msg !== 'TIMEOUT'),
    e05e.closed ? "closed(ok)" : e05e.msg);
  // 清理：若驳回残留模态，Esc 关闭
  if (!e05e.closed) {
    await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))`);
    await new Promise((r) => setTimeout(r, 250));
  }
} else {
  check("改简介模态（无模块数据，跳过）", true);
}

// ---- 工单 06：编辑弹窗（套件 / 链接 + 平台文件增删） ----
const f06 = await Eval(`(() => {
  const btn = document.querySelector('#lib-rows [data-edit-mod]');
  if (!btn) return { skipped: true };
  btn.click();
  return { skipped: false };
})()`);
if (!f06.skipped) {
  const f06b = await Eval(`(async () => {
    await new Promise((r) => setTimeout(r, 250));
    const overlay = document.querySelector('.lib-edit-overlay');
    const sel = overlay && overlay.querySelector('.lib-mod-platform');
    const opts = sel ? [...sel.options].map((o) => o.value) : [];
    const slug = overlay.querySelector('.lib-edit-slug').textContent;
    const mod = (state.modules || []).find((m) => m.slug === slug) || {};
    const plat = opts[0];
    const entry = (mod.platforms || {})[plat] || {};
    const kit = overlay.querySelector('.lib-mod-kit').value;
    const url = overlay.querySelector('.lib-mod-url').value;
    const fileLis = overlay.querySelectorAll('.lib-mod-files li').length;
    const fileNames = [...overlay.querySelectorAll('.lib-mod-files .fname')].map((x) => x.textContent);
    const embedded = !!(entry.files || []).length === false && overlay.querySelector('.lib-mod-files .muted');
    const hasSave = !!overlay.querySelector('.lib-mod-save');
    const hasPush = !!overlay.querySelector('.lib-mod-push');
    // 前端 URL 校验：非法值 → 提示（不发请求）
    overlay.querySelector('.lib-mod-url').value = 'not-a-url';
    overlay.querySelector('.lib-mod-save').click();
    await new Promise((r) => setTimeout(r, 200));
    const msg = overlay.querySelector('.lib-mod-msg').textContent;
    // 还原 url
    overlay.querySelector('.lib-mod-url').value = url;
    return { optCount: opts.length, platNames: Object.keys(mod.platforms || {}).length,
             kitMatch: kit === (entry.kit || ''), urlMatch: url === (entry.source_url || ''),
             fileLis, expFiles: (entry.files || []).length, fileNames, hasSave, hasPush, msg, embedded };
  })()`);
  check("「编辑」→ 模态出现，平台下拉 = 模块平台列表", f06b.optCount === f06b.platNames, `${f06b.optCount} vs ${f06b.platNames}`);
  check("套件 / 链接预填 = 当前平台条目值", f06b.kitMatch && f06b.urlMatch);
  check("文件清单行数 = 条目文件数（内嵌母版态正确）",
    f06b.fileLis === (f06b.expFiles || (f06b.embedded ? 1 : 0)), `lis=${f06b.fileLis} exp=${f06b.expFiles}`);
  check("保存身份 / 推送新文件按钮齐备", f06b.hasSave && f06b.hasPush);
  check("非法 URL → 前端拦截提示（不发请求）", f06b.msg.includes("购买链接格式不正确"), f06b.msg);
  // 内存注入假模块 → 保存身份 → 后端 404 错误路径（不动真实库）
  const f06c = await Eval(`(async () => {
    const base = { description: 'probe', dependencies: [] };
    state.modules = [...(state.modules || []), { ...base, slug: 'probe_edit',
      platforms: { stm32: { files: ['p.c'], verified: false, hardware_bound: false, kit: '', source_url: '' } } }];
    renderLibraryTable();
    await new Promise((r) => setTimeout(r, 250));
    document.querySelector('#lib-rows [data-edit-mod="probe_edit"]').click();
    await new Promise((r) => setTimeout(r, 250));
    const overlay = document.querySelector('.lib-edit-overlay');
    overlay.querySelector('.lib-mod-url').value = 'https://example.com/buy';
    overlay.querySelector('.lib-mod-save').click();
    for (let i = 0; i < 30; i++) {
      await new Promise((r) => setTimeout(r, 200));
      const msg = overlay.querySelector('.lib-mod-msg').textContent;
      if (msg) return { msg, gone: document.querySelectorAll('.lib-edit-overlay').length === 0 };
    }
    return { msg: 'TIMEOUT', gone: false };
  })()`);
  check("假模块保存身份 → 后端错误展示（404 路径，表单保留）",
    f06c.msg && f06c.msg !== 'TIMEOUT' && !f06c.gone, f06c.msg && f06c.msg.slice(0, 60));
  // 关闭清理
  await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))`);
  await new Promise((r) => setTimeout(r, 250));
  const f06d = await Eval(`document.querySelectorAll('.lib-edit-overlay').length`);
  check("Esc 关闭编辑弹窗（无残留）", f06d === 0, `overlay=${f06d}`);
  // 还原内存（去掉假模块，避免影响其他检查）
  await Eval(`state.modules = (state.modules || []).filter((m) => m.slug !== 'probe_edit'); renderLibraryTable();`);
} else {
  check("编辑弹窗（无模块数据，跳过）", true);
}

console.log(failed === 0 ? "SMOKE ALL PASS" : `SMOKE FAILED (${failed})`);
process.exit(failed === 0 ? 0 : 1);
