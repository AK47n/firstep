// 冒烟（reference-library-ui 系列）：参考文件库页 UI。每张工单追加检查项。
// 零依赖：node 内置 fetch + WebSocket 直连 Chrome CDP（9251）；webapp 8000 提供真实 /api/references。
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
      && !!document.getElementById('tab-reference')
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

// ---- 切「参考文件库」tab ----
await Eval(`(() => {
  const tab = [...document.querySelectorAll('nav button, header button, .nav button')]
    .find((b) => b.textContent.trim() === '参考文件库');
  if (tab) tab.click();
  return !!tab;
})()`);
// 轮询等首屏数据就绪（loadReferences 异步 + commit_after_write 耗时；
// 固定等待曾落在加载占位期 → 偶发假 FAIL）
for (let i = 0; i < 40; i++) {
  const n = await Eval(`(refEntryCache || []).length`);
  if (n > 0) break;
  await new Promise((r) => setTimeout(r, 250));
}

const loaded = await Eval(`(refEntryCache || []).length`);
check("参考条目已加载（refEntryCache 非空）", loaded > 0, "entries=" + loaded);

// ================= 工单 02：表格精修 + 客户端即时检索 + 详情弹窗 =================
check("旧筛选区已移除（无 4 输入框 / 无搜索按钮）", await Eval(`!document.getElementById('ref-filter-title')
  && !document.getElementById('btn-ref-search') && !document.getElementById('btn-ref-search-clear')`));

check("工具栏元素齐全（搜索 / 排序 / 方向 / 清空 / 统计 / 两组 chips）", await Eval(`!!(document.getElementById('ref-filter')
  && document.getElementById('ref-sort') && document.getElementById('ref-sort-dir')
  && document.getElementById('ref-filter-clear') && document.getElementById('ref-stats')
  && document.getElementById('ref-platform-chips') && document.getElementById('ref-anchor-chips'))`));

// 防 id 冲突回归（评审 C1）：参考库搜索框用 ref-filter（生成页 picker 的
// ref-search 是另一输入框——getElementById 取 DOM 靠前的那个，重名会绑错元素）
check("参考库搜索框 id 唯一（ref-filter，非生成页 picker 的 ref-search）", await Eval(`(() => {
  const ids = [...document.querySelectorAll('input[id]')].map((i) => i.id);
  return ids.filter((i) => i === 'ref-filter').length === 1
    && ids.filter((i) => i === 'ref-search').length === 1
    && document.querySelector('#tab-reference input#ref-filter') !== null;
})()`));

const t02c = await Eval(`(() => {
  const table = document.querySelector('#tab-reference table');
  const th = document.querySelector('#tab-reference thead th');
  const rows = document.querySelectorAll('#ref-rows tr').length;
  return { hasLibTable: !!(table && table.classList.contains('lib-table')),
    thBg: th ? getComputedStyle(th).backgroundColor : null, rows };
})()`);
check("表格带 lib-table 类", t02c.hasLibTable);
check("表头有底纹背景", !!t02c.thBg && t02c.thBg !== "rgba(0, 0, 0, 0)", "bg=" + t02c.thBg);
check("行数 = 全量条目数", t02c.rows === loaded, `rows=${t02c.rows}, entries=${loaded}`);

const t02e = await Eval(`(() => {
  const first = document.querySelector('#ref-rows tr');
  if (!first) return null;
  const titleTd = first.querySelector('.ref-title-cell');
  const descTd = first.querySelector('.desc-cell');
  const badge = first.querySelector('.badge');
  const btnView = first.querySelector('[data-ref-view]');
  const btnDel = first.querySelector('button.danger[data-ref-del]');
  return { titleFull: titleTd ? (titleTd.title || '') : '', titleClass: !!titleTd,
    descTitle: descTd ? (descTd.title || '') : '',
    badgeClass: badge ? badge.className : null,
    btnViewText: btnView ? btnView.textContent.trim() : null, hasDel: !!btnDel };
})()`);
check("首行标题列截断类 + 全文 tooltip", !!(t02e && t02e.titleClass && t02e.titleFull), t02e && t02e.titleFull);
check("首行简介列 tooltip 全文", !!(t02e && t02e.descTitle), t02e && t02e.descTitle);
check("首行锚定徽章（ref-topic / ref-kit / ref-none）", !!(t02e && t02e.badgeClass && /badge ref-(topic|kit|none)/.test(t02e.badgeClass)), t02e && t02e.badgeClass);
check("操作列：详情 + danger 删除", !!(t02e && t02e.btnViewText === "详情" && t02e.hasDel));

// ---- 统计条（全量口径；工单 04 追加悬空红段，故用「包含」而非严格相等） ----
const t02f = await Eval(`(() => {
  const text = document.getElementById('ref-stats').textContent;
  const expected = refStatsText(refStats(refEntryCache));
  return { text, expected, match: text.includes(expected) };
})()`);
check("统计条文案含 refStatsText(refStats(全量))", t02f.match, t02f.text);

// ---- 关键字即时过滤（防抖 150ms） ----
const qProbe = await Eval(`(refEntryCache[0].title || '').slice(0, 4)`);
await Eval(`(() => {
  const inp = document.getElementById('ref-filter');
  inp.value = ${JSON.stringify(qProbe)};
  inp.dispatchEvent(new Event('input', { bubbles: true }));
})()`);
await new Promise((r) => setTimeout(r, 500));
const t02g = await Eval(`(() => {
  const rows = [...document.querySelectorAll('#ref-rows tr')];
  const expected = refFilterEntries(refEntryCache, { q: ${JSON.stringify(qProbe)}, platform: '', anchorKind: '' });
  return { n: rows.length, exp: expected.length, qState: refUI.q,
    firstTitle: rows.length ? rows[0].querySelector('.ref-title-cell').textContent.trim() : null,
    expFirstTitle: expected.length ? expected[0].title : null };
})()`);
check("关键字过滤行数 = 纯函数期望", t02g.n === t02g.exp, `n=${t02g.n}, exp=${t02g.exp}`);
check("防抖态 refUI.q 已更新（真实绑定到参考库输入框）", t02g.qState === qProbe, "q=" + t02g.qState);
check("过滤后首行标题 = 期望首条", t02g.firstTitle === t02g.expFirstTitle, `${t02g.firstTitle} vs ${t02g.expFirstTitle}`);

// ---- 平台 chips 过滤（mspm0）与统计联动 ----
// 先彻底清空过滤（清空按钮 = refUI.q/platform/anchorKind + 输入框值全重置，
// 只设 value 会遗留防抖态 refUI.q，期望值以空 q 计算必然不一致）
await Eval(`document.getElementById('ref-filter-clear').click()`);
await new Promise((r) => setTimeout(r, 300));
await Eval(`(() => {
  const chip = [...document.querySelectorAll('#ref-platform-chips .lib-chip')]
    .find((b) => b.getAttribute('data-ref-chip') === 'mspm0');
  if (chip) chip.click();
})()`);
await new Promise((r) => setTimeout(r, 300));
const t02h = await Eval(`(() => {
  const rows = document.querySelectorAll('#ref-rows tr').length;
  const expected = refFilterEntries(refEntryCache, { q: '', platform: 'mspm0', anchorKind: '' });
  const on = document.querySelector('#ref-platform-chips .lib-chip.on');
  const statsText = document.getElementById('ref-stats').textContent;
  const statsExpected = refStatsText(refStats(refFilterEntries(refEntryCache, { q: '', platform: 'mspm0', anchorKind: '' })));
  return { n: rows, exp: expected.length, onVal: on ? on.getAttribute('data-ref-chip') : null,
    statsText, statsExpected };
})()`);
check("平台 chip（mspm0）过滤行数 = 期望", t02h.n === t02h.exp, `n=${t02h.n}, exp=${t02h.exp}`);
check("选中 chip 带 on 态", t02h.onVal === "mspm0", t02h.onVal);
check("统计条随过滤联动 = 纯函数期望（含悬空段）", t02h.statsText.includes(t02h.statsExpected), t02h.statsText);

// ---- 锚定类型 chips 过滤（未锚定） ----
await Eval(`document.querySelector('#ref-platform-chips .lib-chip.on').click()`);
await Eval(`(() => {
  const chip = [...document.querySelectorAll('#ref-anchor-chips .lib-chip')]
    .find((b) => b.getAttribute('data-ref-chip') === 'none');
  if (chip) chip.click();
})()`);
await new Promise((r) => setTimeout(r, 300));
const t02i = await Eval(`(() => {
  const n = document.querySelectorAll('#ref-rows tr').length;
  const exp = refFilterEntries(refEntryCache, { q: '', platform: '', anchorKind: 'none' }).length;
  const anyNone = [...document.querySelectorAll('#ref-rows .badge')].every((b) => b.className.includes('ref-none'));
  return { n, exp, anyNone };
})()`);
check("锚定 chip（未锚定）过滤行数 = 期望且全为未锚定徽章", t02i.n === t02i.exp && t02i.anyNone, `n=${t02i.n}, exp=${t02i.exp}`);
await Eval(`document.getElementById('ref-filter-clear').click()`);
await new Promise((r) => setTimeout(r, 300));

// ---- 排序（体量降序）与方向切换 ----
await Eval(`(() => {
  const sel = document.getElementById('ref-sort');
  sel.value = 'size';
  sel.dispatchEvent(new Event('change', { bubbles: true }));
})()`);
await Eval(`document.getElementById('ref-sort-dir').click()`);
await new Promise((r) => setTimeout(r, 300));
const t02j = await Eval(`(() => {
  const rows = [...document.querySelectorAll('#ref-rows tr')];
  const exp = refSortEntries(refEntryCache, { by: 'size', dir: 'desc' });
  const first = rows.length ? rows[0].querySelector('.ref-title-cell').textContent.trim() : null;
  const dirText = document.getElementById('ref-sort-dir').textContent;
  return { first, expFirst: exp.length ? exp[0].title : null, dirText };
})()`);
check("体量降序首行标题 = 期望", t02j.first === t02j.expFirst, `${t02j.first} vs ${t02j.expFirst}`);
check("排序方向按钮文案已切换（↓ 降序）", t02j.dirText.includes("↓"), t02j.dirText);

// ---- 空态（无匹配）与清空恢复 ----
await Eval(`(() => {
  const inp = document.getElementById('ref-filter');
  inp.value = 'ZZZZ无此词ZZZZ';
  inp.dispatchEvent(new Event('input', { bubbles: true }));
})()`);
await new Promise((r) => setTimeout(r, 500));
const t02n = await Eval(`document.querySelector('#ref-rows .es-title')?.textContent || ''`);
check("无匹配空态提示", t02n.includes("没有匹配"), t02n);
await Eval(`document.getElementById('ref-filter-clear').click()`);
await new Promise((r) => setTimeout(r, 300));
check("清空过滤恢复全量行数", await Eval(`document.querySelectorAll('#ref-rows tr').length === refEntryCache.length`));

// ---- 详情弹窗（元数据段 + 文件清单段） ----
await Eval(`document.querySelector('#ref-rows [data-ref-view]').click()`);
await new Promise((r) => setTimeout(r, 700));
const t02l = await Eval(`(() => {
  const overlay = document.querySelector('.ref-files-overlay');
  if (!overlay) return null;
  const meta = overlay.querySelector('.ref-detail-meta');
  const title = meta ? meta.querySelector('.ref-detail-title') : null;
  const rows = meta ? meta.querySelectorAll('.ref-detail-row').length : 0;
  const listItems = overlay.querySelectorAll('.ref-files-list li[data-path]').length;
  const filter = overlay.querySelector('.ref-files-filter');
  const headText = overlay.querySelector('.ref-files-head strong').textContent;
  return { title: title ? title.textContent : null, rows, listItems, hasFilter: !!filter, headText };
})()`);
check("详情弹窗已打开（遮罩 + 头部）", !!(t02l && t02l.headText.includes("参考条目详情")), t02l && t02l.headText);
check("元数据段：标题 + 5 行（编号/类型/锚定/简介/体量）", !!(t02l && t02l.title && t02l.rows === 5), t02l && `rows=${t02l && t02l.rows}`);
check("文件清单段：过滤输入 + 路径列表（磁盘实况）", !!(t02l && t02l.hasFilter && t02l.listItems > 0), t02l && `items=${t02l && t02l.listItems}`);

// 详情内文件过滤
const t02m = await Eval(`(async () => {
  const overlay = document.querySelector('.ref-files-overlay');
  const first = overlay.querySelector('.ref-files-list li[data-path]');
  const needle = (first.dataset.path || '').slice(0, 5);
  const inp = overlay.querySelector('.ref-files-filter');
  inp.value = needle;
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 100));
  const visible = [...overlay.querySelectorAll('.ref-files-list li[data-path]')]
    .filter((li) => li.style.display !== 'none').length;
  return { needle, visible, total: overlay.querySelectorAll('.ref-files-list li[data-path]').length };
})()`);
check("详情文件过滤：可见数 ≤ 总数且命中", t02m.visible >= 1 && t02m.visible <= t02m.total, `vis=${t02m.visible}/${t02m.total} needle=${t02m.needle}`);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))`);
await new Promise((r) => setTimeout(r, 200));
check("Esc 关闭详情弹窗", await Eval(`!document.querySelector('.ref-files-overlay')`));

// ================= 工单 03：编辑弹窗（改元数据 + 文件增删，一次 PUT） =================
// 用「临时条目」流：add → edit → 持久化验证 → delete；finally 兜底清理（幂等：
// 先清历史残留的同名前缀条目再新建，重复跑不累积污染）。真实数据零改动。
const TMP_TITLE = "冒烟临时-编辑条目";
const cleanupTmp = async () => {
  try {
    await Eval(`(async () => {
      const all = await (await fetch('/api/references')).json();
      for (const e of all) {
        if ((e.title || '').startsWith('${TMP_TITLE}')) {
          await fetch('/api/references/' + encodeURIComponent(e.id), { method: 'DELETE' });
        }
      }
      return 'ok';
    })()`);
  } catch {}
};
try {
  // 幂等：清历史残留 → 新建临时条目
  await cleanupTmp();
  const tmpId = await Eval(`(async () => {
    const r = await fetch('/api/references', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: '${TMP_TITLE}', type: '冒烟测试', description: '工单 03 冒烟专用，脚本结束后删除',
        anchor_kind: 'none', anchor_value: '', platform: 'any', files: { 'demo.txt': '冒烟临时文件' },
      }),
    });
    if (!r.ok) throw new Error('add 失败 ' + r.status + ' ' + (await r.text()));
    const entry = await r.json();
    if (typeof loadReferences === 'function') loadReferences();
    return entry.id;
  })()`);
  await new Promise((r) => setTimeout(r, 700));

  // 打开编辑弹窗（按 id 找行内「编辑」按钮）
  await Eval(`(() => {
    const b = document.querySelector('#ref-rows [data-ref-edit="${tmpId}"]');
    if (b) b.click();
    return !!b;
  })()`);
  await new Promise((r) => setTimeout(r, 600));
  const t03a = await Eval(`(() => {
    const overlay = document.querySelector('.lib-edit-overlay');
    if (!overlay) return null;
    const head = overlay.querySelector('.ref-edit-id');
    const title = overlay.querySelector('.ref-edit-title');
    const kind = overlay.querySelector('.ref-edit-kind');
    const desc = overlay.querySelector('.ref-edit-desc');
    return { head: head ? head.textContent : null, title: title ? title.value : null,
      kind: kind ? kind.value : null, hasSave: !!overlay.querySelector('.ref-edit-save'),
      hasFiles: !!overlay.querySelector('.ref-edit-files') };
  })()`);
  check("编辑弹窗打开，头部 = 条目 id", !!(t03a && t03a.head === tmpId), t03a && t03a.head);
  check("编辑弹窗预填标题 / 锚定 / 简介", !!(t03a && t03a.title === TMP_TITLE && t03a.kind === 'none'), t03a && t03a.title);
  check("编辑弹窗：保存按钮 + 文件清单区就位", !!(t03a && t03a.hasSave && t03a.hasFiles));

  // 改标题 + 简介 + 勾选删除 demo.txt → 保存（一次 PUT：元数据 + remove_files）
  const NEW_TITLE = TMP_TITLE + "-改";
  await Eval(`(() => {
    const o = document.querySelector('.lib-edit-overlay');
    o.querySelector('.ref-edit-title').value = '${NEW_TITLE}';
    o.querySelector('.ref-edit-desc').value = '工单 03 已编辑（冒烟验证持久化）';
    const rm = o.querySelector('[data-edit-rm]');
    if (rm) rm.checked = true;
    o.querySelector('.ref-edit-save').click();
  })()`);
  await new Promise((r) => setTimeout(r, 900));
  // 保存后 loadReferences 异步重取全量（含 commit_after_write 的 git 提交耗时）：
  // 轮询等 refEntryCache 更新到新标题（最多 5s），避免固定等待落在加载占位期
  let t03b = null;
  for (let i = 0; i < 50; i++) {
    t03b = await Eval(`(() => {
      const cache = (refEntryCache || []).find((e) => e.id === '${tmpId}');
      const rowTitle = [...document.querySelectorAll('#ref-rows [data-ref-edit="${tmpId}"]')].length
        ? document.querySelector('#ref-rows [data-ref-edit="${tmpId}"]').closest('tr')
            .querySelector('.ref-title-cell').textContent.trim() : null;
      return { overlayGone: !document.querySelector('.lib-edit-overlay'),
        cacheTitle: cache ? cache.title : null, rowTitle };
    })()`);
    if (t03b.cacheTitle === NEW_TITLE && t03b.overlayGone) break;
    await new Promise((r) => setTimeout(r, 100));
  }
  check("保存成功：弹窗关闭 + refEntryCache 更新", !!(t03b.overlayGone && t03b.cacheTitle === NEW_TITLE), t03b.cacheTitle);
  check("保存成功：表格行即时刷新新标题", t03b.rowTitle === NEW_TITLE, t03b.rowTitle);
  const t03b2 = await Eval(`fetch('/api/references/${tmpId}/files').then((r) => r.json()).then((f) => f.length)`);
  check("勾选删除文件生效（磁盘实况端点 files 已空）", t03b2 === 0, "files=" + t03b2);

  // 持久化：刷新页面后仍为已改标题
  await Eval(`window.__smokeMarker = 1`);
  await cdp("Page.reload", { ignoreCache: true });
  let ready2 = false;
  for (let i = 0; i < 100 && !ready2; i++) {
    try {
      ready2 = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
        && typeof loadReferences === 'function'`);
    } catch {}
    if (!ready2) await new Promise((r) => setTimeout(r, 300));
  }
  await Eval(`loadReferences()`);
  await new Promise((r) => setTimeout(r, 900));
  const t03c = await Eval(`(() => {
    const e = (refEntryCache || []).find((x) => x.id === '${tmpId}');
    return e ? e.title : null;
  })()`);
  check("刷新页面后编辑仍持久（GET 回读新标题）", t03c === NEW_TITLE, t03c);
} finally {
  await cleanupTmp();
  await new Promise((r) => setTimeout(r, 500));
}
const t03d = await Eval(`(async () => {
  const all = await (await fetch('/api/references')).json();
  return all.some((e) => (e.title || '').startsWith('${TMP_TITLE}'));
})()`);
check("临时条目已清理（真实库零残留，服务器直查）", t03d === false);

// ================= 工单 04：悬空锚定警示 =================
// 确保全量态 + 悬空判定数据源就绪（赛题库 key / kit 词表）
await Eval(`(() => {
  const tab = [...document.querySelectorAll('nav button, header button, .nav button')]
    .find((b) => b.textContent.trim() === '参考文件库');
  if (tab) tab.click();
})()`);
await new Promise((r) => setTimeout(r, 600));
await Eval(`Promise.all([loadReferences(), loadKitVocabulary()])`);
await new Promise((r) => setTimeout(r, 900));

const t04a = await Eval(`(() => ({ topics: (refTopicKeys || []).length, kits: (kitVocabulary || []).length }))()`);
check("悬空判定数据源就绪（赛题库 key / kit 词表已拉取且非空）", t04a.topics > 0 && t04a.kits > 0, `topics=${t04a.topics}, kits=${t04a.kits}`);

// 期望值 = 页面内纯函数（与 DOM 比对；赛题库空 / 词表空 = 降级零误报也 PASS）
const t04b = await Eval(`(() => {
  const exp = refDanglingAnchors(refEntryCache, refTopicKeys, kitVocabulary);
  const withTag = [...document.querySelectorAll('#ref-rows tr')]
    .filter((tr) => tr.querySelector('.ref-dangling-tag')).length;
  const red = document.querySelector('#ref-stats [data-ref-dangling]');
  return { exp: exp.length, withTag, hasRed: !!red, redText: red ? red.textContent : null };
})()`);
check("行内 ⚠ 数 = 悬空条目数", t04b.withTag === t04b.exp, `withTag=${t04b.withTag}, exp=${t04b.exp}`);
check("统计条红色悬空段（0 时不渲染红色形态）", t04b.hasRed === (t04b.exp > 0), t04b.redText || "none");

// 红段点击过滤（只显示悬空）→ 再点取消（与过滤 / 排序正交）
if (t04b.exp > 0) {
  await Eval(`document.querySelector('#ref-stats [data-ref-dangling]').click()`);
  await new Promise((r) => setTimeout(r, 400));
  const t04c = await Eval(`(() => {
    const n = document.querySelectorAll('#ref-rows tr').length;
    // 期望 = 悬空集本身（dangling 过滤后即悬空条目；refUI 无词表故不可复用 refFilterEntries 算期望）
    const exp = refDanglingAnchors(refEntryCache, refTopicKeys, kitVocabulary).length;
    return { n, exp, on: refUI.dangling };
  })()`);
  check("点击红段：只显示悬空条目", t04c.on && t04c.n === t04c.exp, `n=${t04c.n}, exp=${t04c.exp}`);
  await Eval(`document.querySelector('#ref-stats [data-ref-dangling]').click()`);
  await new Promise((r) => setTimeout(r, 400));
  check("再点取消：恢复全量", await Eval(`!refUI.dangling && document.querySelectorAll('#ref-rows tr').length === refEntryCache.length`));
} else {
  check("空库降级分支：红段未渲染（跳过点击验证）", true);
}

// 编辑闭环：临时 topic 悬空条目（格式合法但赛题库不存在的编号）→ ⚠ 出现 →
// 编辑改未锚定 → ⚠ 消失 → finally 清理（真实数据零改动）
const D_TITLE = "冒烟悬空-临时条目";
const cleanupD = async () => {
  try {
    await Eval(`(async () => {
      const all = await (await fetch('/api/references')).json();
      for (const e of all) {
        if ((e.title || '').startsWith('${D_TITLE}')) {
          await fetch('/api/references/' + encodeURIComponent(e.id), { method: 'DELETE' });
        }
      }
      return 'ok';
    })()`);
  } catch {}
};
try {
  await cleanupD();
  const dId = await Eval(`(async () => {
    let last = null;
    for (const av of ['1999Z', '2099Z', '2088Z']) {
      const r = await fetch('/api/references', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: '${D_TITLE}', type: '冒烟测试',
          description: '悬空警示冒烟，脚本结束后删除', anchor_kind: 'topic', anchor_value: av,
          platform: 'any', files: { 'demo.txt': 'x' } }),
      });
      if (r.ok) { const e = await r.json(); return { ...e, tried: [av] }; }
      last = av;
    }
    throw new Error('所有候选悬空编号都被拒（最后: ' + last + '）');
  })()`);
  await Eval(`loadReferences()`);
  let foundTag = false;
  for (let i = 0; i < 40; i++) {
    foundTag = await Eval(`(() => {
      const tr = document.querySelector('#ref-rows [data-ref-edit="${dId.id}"]');
      if (!tr) return false;
      return !!tr.closest('tr').querySelector('.ref-dangling-tag');
    })()`);
    if (foundTag) break;
    await new Promise((r) => setTimeout(r, 200));
  }
  check("悬空临时条目行内 ⚠（topic 锚定未被任何赛题 key 命中）", foundTag, dId.tried[0]);

  // 编辑 → 改未锚定 → 保存 → ⚠ 消失
  await Eval(`(() => {
    const b = document.querySelector('#ref-rows [data-ref-edit="${dId.id}"]');
    if (b) b.click();
  })()`);
  await new Promise((r) => setTimeout(r, 600));
  await Eval(`(() => {
    const o = document.querySelector('.lib-edit-overlay');
    const k = o.querySelector('.ref-edit-kind');
    k.value = 'none';
    k.dispatchEvent(new Event('change', { bubbles: true }));
    o.querySelector('.ref-edit-save').click();
  })()`);
  let gone = false;
  for (let i = 0; i < 50; i++) {
    gone = await Eval(`(() => {
      const tr = document.querySelector('#ref-rows [data-ref-edit="${dId.id}"]');
      if (!tr) return false;
      return !tr.closest('tr').querySelector('.ref-dangling-tag');
    })()`);
    if (gone) break;
    await new Promise((r) => setTimeout(r, 200));
  }
  check("编辑改未锚定保存后 ⚠ 消失（警示闭环）", gone);
} finally {
  await cleanupD();
}

console.log(failed ? `SMOKE FAILED(${failed})` : "SMOKE ALL PASS");
process.exit(failed ? 1 : 0);
