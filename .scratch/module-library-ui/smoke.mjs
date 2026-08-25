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

console.log(failed === 0 ? "SMOKE ALL PASS" : `SMOKE FAILED (${failed})`);
process.exit(failed === 0 ? 0 : 1);
