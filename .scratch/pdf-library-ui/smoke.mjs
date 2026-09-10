// 冒烟（pdf-library-ui 系列，工单 02–06）：PDF 资料库页 UI——表格精修 + 客户端
// 即时检索/排序/统计 / 轻量详情弹窗（页数懒取 + 复制相对路径）/ 数据健康
// （疑似重复 + 0 字节损坏）/ 空态与清空恢复 / 疑似重复回收删除（单删 + 组级）。
//
// 重写说明（2026-09-09 第八轮「未完成」第 1 项）：本脚本写于前端阶段 2 ES 模块化
// **之前**，就绪判据与断言直接求值 `pdfCache` / `pdfFilterContext()` / `loadPdfs()`
// 等**模块作用域名**——模块化后不再挂全局（`app.js` 规则 3：不挂 window 桥），
// 求值抛错 → 就绪判据恒假 → 脚本退出「页面未就绪」。本轮按已绿的
// `.scratch/master-library-ui-2/smoke.mjs` 模板重写：cdp-harness（每支前重建标签页
// + 自动应答 beforeunload + 命令超时）+ 数据取真实端点 + 期望值由**页面内
// `import()` 取纯件**现算 + 就绪/断言全部用 DOM 可观察事实；需要触发重渲染时调
// ui 模块的**导出**函数（`import('/js/ui/pdf.js')` → `loadPdfs`）。
// 零真删真实素材：只真删本脚本自建的 zz-smoke-* 合成文件（同名同大小对 → 重复组），
// finally 里连回收镜像一起清理；真实素材零触碰。
import { mkdirSync, writeFileSync, unlinkSync, rmSync, existsSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const PAGE_URL = "http://127.0.0.1:8000/";
const MATERIALS = join(ROOT, "sources", "materials");
const TRASH = join(ROOT, "sources", ".trash-pdf");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const dateStr = (() => {
  const t = new Date(), p = (n) => String(n).padStart(2, "0");
  return `${t.getFullYear()}-${p(t.getMonth() + 1)}-${p(t.getDate())}`;
})();

await rebuildTab({ port: CDP, pageUrl: PAGE_URL, settleMs: 2000 });
const c = await connect({ port: CDP, pageUrl: PAGE_URL, timeoutMs: 20000 });
await c.cdp("Page.enable");
const Eval = (expr) => c.Eval(expr);

// 页面内探针命名空间（仅本次运行时注入，不落产品代码）：纯件 + ui 导出 + 真实数据
await Eval(`(async () => {
  const [core, fx] = await Promise.all([import('/js/fx/core.js'), import('/js/fx/pdf.js')]);
  const ui = { pdf: await import('/js/ui/pdf.js') };
  window.__probe = { core, fx, ui,
    pdfs: await (await fetch('/api/pdfs')).json(),
    reload: async () => {
      window.__probe.pdfs = await (await fetch('/api/pdfs')).json();
      await window.__probe.ui.pdf.loadPdfs();
      return window.__probe.pdfs.length;
    } };
  return window.__probe.pdfs.length;
})()`);

const ready = await c.ready(`document.readyState === 'complete'
  && !!document.getElementById('tab-pdf') && !!document.getElementById('pdf-rows')
  && !!window.__probe && Array.isArray(window.__probe.pdfs)`, 20000);
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};
// 期望值单源 = 页面内纯件 + 真实端点数据
const expect = (expr) => Eval(`(() => { const P = window.__probe; const pdfs = P.pdfs; const fx = P.fx;
  const { pdfFilterEntries, pdfSortEntries, pdfStats, pdfStatsText, pdfHealth, pdfBroken, formatMtime } = fx;
  const { formatSize } = P.core;
  const h = pdfHealth(pdfs);
  return (${expr}); })()`);

// ---- 切「PDF 资料库」tab（host 分发器跑 loadPdfs → 真实端点全量） ----
const total = await Eval(`window.__probe.pdfs.length`);
await Eval(`(() => {
  const tab = [...document.querySelectorAll('nav button')].find((b) => b.dataset.tab === 'pdf');
  if (tab) tab.click();
  return !!tab;
})()`);
const rowsLoaded = await c.waitFor(`document.querySelectorAll('#pdf-rows tr').length === ${total}`, 20000);
check("PDF 列表已加载（真实素材库全量行数）", rowsLoaded, "pdfs=" + total);

// ================= 工单 02：表格精修 + 检索 + 排序 + 统计 =================
check("旧筛选区已移除（无搜索/清空按钮、无计数 span、无 pdf-count）", await Eval(`
  !document.getElementById('btn-pdf-search') && !document.getElementById('btn-pdf-search-clear')
  && !document.getElementById('pdf-count')`));
check("工具栏元素齐全（搜索 / 排序 / 方向 / 清空 / 刷新 / 批次 chips / 统计条）", await Eval(`
  !!(document.getElementById('pdf-filter') && document.getElementById('pdf-sort')
    && document.getElementById('pdf-sort-dir') && document.getElementById('pdf-filter-clear')
    && document.getElementById('pdf-refresh') && document.getElementById('pdf-batch-chips')
    && document.getElementById('pdf-stats'))`));
check("pdf- 前缀元素 id 全局唯一（≥10 个，无重复）", await Eval(`(() => {
  const ids = [...document.querySelectorAll('[id^="pdf-"]')].map((i) => i.id);
  return ids.length === new Set(ids).size && ids.length >= 10; })()`));

const t02c = await Eval(`(() => {
  const table = document.querySelector('#tab-pdf table');
  const th = document.querySelector('#tab-pdf thead th');
  return { hasLibTable: !!table && table.classList.contains('lib-table'),
    thBg: th ? getComputedStyle(th).backgroundColor : null,
    ths: [...document.querySelectorAll('#tab-pdf thead th')].map((t) => t.textContent.trim()) };
})()`);
check("表格带 lib-table 类", t02c.hasLibTable);
check("表头有底纹背景", !!t02c.thBg && t02c.thBg !== "rgba(0, 0, 0, 0)", "bg=" + t02c.thBg);
check("表头 6 列（文件名/批次/目录/大小/修改时间/操作）",
  JSON.stringify(t02c.ths) === JSON.stringify(["文件名", "批次", "目录", "大小", "修改时间", "操作"]),
  t02c.ths.join("/"));

// 默认排序 = 最近更新降序（pdfUI 初值 mtime/desc，与 select 的 selected 项一致）
const t02d = await Eval(`(() => {
  const first = document.querySelector('#pdf-rows tr');
  const nameTd = first.querySelector('.desc-cell');
  const tds = [...first.querySelectorAll('td')];
  return {
    name: nameTd.querySelector('a').textContent.trim(),
    nameTitle: nameTd.getAttribute('title') || '',
    chip: (first.querySelector('.lib-chip') || {}).textContent || '',
    sizeText: tds[3].textContent.trim(),
    mtimeText: tds[4].textContent.trim(),
    btnOpen: (first.querySelector('button[data-open-pdf]') || {}).textContent || '',
    btnDetail: (first.querySelector('[data-pdf-detail]') || {}).textContent || '',
    sortVal: document.getElementById('pdf-sort').value,
    dirText: document.getElementById('pdf-sort-dir').textContent,
  };
})()`);
const expFirst = await expect(`(() => { const p = pdfSortEntries(pdfs, { by: 'mtime', dir: 'desc' })[0];
  return { name: p.name, rel: p.rel_path, size: formatSize(p.size_bytes), mtime: formatMtime(p.mtime), batch: p.batch }; })()`);
check("默认排序 = 最近更新降序（select 值 + 方向按钮文案）",
  t02d.sortVal === "mtime" && t02d.dirText.includes("↓"), `${t02d.sortVal} / ${t02d.dirText}`);
check("首行 = 纯件默认排序首条（名称 / 大小 / 时间 / tooltip 全路径）",
  t02d.name === expFirst.name && t02d.sizeText === expFirst.size
    && t02d.mtimeText === expFirst.mtime && t02d.nameTitle === expFirst.rel,
  `${t02d.name} | ${t02d.sizeText} vs ${expFirst.size}`);
check("首行批次 chip + 操作列「打开 / 详情」",
  t02d.chip.includes(expFirst.batch) && t02d.btnOpen === "打开" && t02d.btnDetail === "详情",
  `${t02d.chip} | ${t02d.btnOpen}/${t02d.btnDetail}`);
check("修改时间列格式 YYYY-MM-DD HH:mm", /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(t02d.mtimeText), t02d.mtimeText);

const expStats = await expect(`pdfStatsText(pdfStats(pdfs))`);
check("统计条 = 全量纯件口径（共 N 份 · 总体积 · 批次）", await Eval(`
  document.getElementById('pdf-stats').textContent.includes(${JSON.stringify(expStats)})`), expStats);

// ---- 关键字即时过滤（防抖 150ms）：派发当帧不重渲染 → 防抖后按纯件收缩 ----
const kwProbe = "数据手册";
const kw = await Eval(`(async () => {
  const inp = document.getElementById('pdf-filter');
  inp.value = ${JSON.stringify(kwProbe)};
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  const immediate = document.querySelectorAll('#pdf-rows tr').length;
  await new Promise((r) => setTimeout(r, 450));
  return { immediate, after: document.querySelectorAll('#pdf-rows tr').length };
})()`);
const expKw = await expect(`pdfFilterEntries(pdfs, { q: ${JSON.stringify(kwProbe)}, batch: '', health: '' }).length`);
check("关键字即时过滤：命中数 = 纯件期望且 < 全量",
  kw.after === expKw && kw.after > 0 && kw.after < total, `${kw.after} vs ${expKw} / 全量 ${total}`);
check("防抖 150ms 生效（派发 input 后当帧不重渲染）", kw.immediate === total, `immediate=${kw.immediate}`);
await Eval(`document.getElementById('pdf-filter-clear').click()`);
await c.waitFor(`document.querySelectorAll('#pdf-rows tr').length === ${total}`, 8000);
check("清空过滤恢复全量", await Eval(`document.querySelectorAll('#pdf-rows tr').length === ${total}`));

// ---- 批次 chips：点击过滤（行数 = 该批次份数）→ 再点取消 ----
const chipTest = await Eval(`(async () => {
  const btn = [...document.querySelectorAll('#pdf-batch-chips [data-pdf-chip]')]
    .find((b) => b.dataset.pdfChip !== '');
  if (!btn) return { skipped: true };
  const batch = btn.dataset.pdfChip;
  btn.click();
  await new Promise((r) => setTimeout(r, 250));
  const filtered = document.querySelectorAll('#pdf-rows tr').length;
  const on = document.querySelector('#pdf-batch-chips .lib-chip.on');
  const onVal = on ? on.dataset.pdfChip : null;
  const btn2 = [...document.querySelectorAll('#pdf-batch-chips [data-pdf-chip]')]
    .find((b) => b.dataset.pdfChip === batch);
  if (btn2) btn2.click();
  await new Promise((r) => setTimeout(r, 250));
  return { skipped: false, batch, filtered, onVal,
    restored: document.querySelectorAll('#pdf-rows tr').length };
})()`);
if (!chipTest.skipped) {
  const expBatch = await expect(`pdfFilterEntries(pdfs, { q: '', batch: ${JSON.stringify(chipTest.batch)}, health: '' }).length`);
  check("批次 chip 点击 = 只看该批次（行数 = 纯件期望 + on 态）",
    chipTest.filtered === expBatch && chipTest.filtered > 0 && chipTest.onVal === chipTest.batch,
    `${chipTest.batch}: ${chipTest.filtered}/${expBatch}`);
  check("批次 chip 再点取消 = 恢复全量", chipTest.restored === total, "rows=" + chipTest.restored);
} else {
  check("批次 chip 过滤（无批次数据，跳过）", true);
}

// ---- 排序切换：按大小（默认方向 = 降序）→ 全列序列 = 纯件期望；再点方向 → 升序 ----
const sortTest = await Eval(`(async () => {
  const seq = () => [...document.querySelectorAll('#pdf-rows tr')]
    .map((tr) => tr.querySelector('.desc-cell').getAttribute('title'));
  const sel = document.getElementById('pdf-sort');
  sel.value = 'size';
  sel.dispatchEvent(new Event('change', { bubbles: true }));   // 方向保持当前（降序）
  await new Promise((r) => setTimeout(r, 300));
  const descSeq = seq();
  document.getElementById('pdf-sort-dir').click();             // ↓ → ↑
  await new Promise((r) => setTimeout(r, 300));
  return { descSeq, ascSeq: seq(), dirText: document.getElementById('pdf-sort-dir').textContent };
})()`);
const expSortDesc = await expect(`pdfSortEntries(pdfs, { by: 'size', dir: 'desc' }).map((p) => p.rel_path)`);
const expSortAsc = await expect(`pdfSortEntries(pdfs, { by: 'size', dir: 'asc' }).map((p) => p.rel_path)`);
check("排序（大小降序）：全行序列与纯件完全一致",
  JSON.stringify(sortTest.descSeq) === JSON.stringify(expSortDesc),
  `first=${sortTest.descSeq[0]}`);
check("排序方向切换（↑ 升序）：全行序列与纯件完全一致，方向按钮文案跟随",
  JSON.stringify(sortTest.ascSeq) === JSON.stringify(expSortAsc) && sortTest.dirText.includes("↑"),
  `first=${sortTest.ascSeq[0]} / ${sortTest.dirText}`);
await Eval(`(() => { const s = document.getElementById('pdf-sort');
  s.value = 'mtime'; s.dispatchEvent(new Event('change', { bubbles: true })); })()`);   // 回默认（mtime/desc）
await sleep(300);

// ================= 工单 03：轻量详情弹窗（页数懒取 + 复制相对路径） =================
const detailRel = await Eval(`window.__probe.pdfs[0].rel_path`);
const detailSel = `#pdf-rows [data-pdf-detail="${detailRel}"]`;
const d03 = await Eval(`(async () => {
  const btn = document.querySelector(${JSON.stringify(detailSel)});
  if (!btn) return { found: false };
  btn.click();
  for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 200));
    const t = document.querySelector('.ref-files-overlay [data-pdf-pages]')?.textContent || '';
    if (t && !t.includes('读取中')) break;
  }
  const ov = document.querySelector('.ref-files-overlay');
  const out = {
    found: true, overlayCount: document.querySelectorAll('.ref-files-overlay').length,
    text: ov.textContent,
    pagesText: ov.querySelector('[data-pdf-pages]')?.textContent || '',
    hasCopySlot: !!ov.querySelector('.pdf-detail-copy-msg'),
    hasOpen: !!ov.querySelector('[data-pdf-open]'),
  };
  ov.querySelector('.ref-files-close').click();
  await new Promise((r) => setTimeout(r, 250));
  out.closedByX = document.querySelectorAll('.ref-files-overlay').length === 0;
  return out;
})()`);
check("详情弹窗打开（行「详情」→ 遮罩弹窗，替换式唯一）",
  d03.found && d03.overlayCount === 1, `overlay=${d03.overlayCount}`);
check("详情含完整相对路径 + 打开按钮 + 复制消息槽",
  d03.text.includes(detailRel) && d03.hasOpen && d03.hasCopySlot, detailRel);
check("页数懒取：真实文件成功显示 N 页（非「读取中」/「无法读取」）",
  /\d+ 页/.test(d03.pagesText) && !d03.pagesText.includes("无法读取"), d03.pagesText);
check("× 关闭弹窗（无残留）", d03.closedByX);

// 复制相对路径 → 消息槽反馈（已复制 / 降级失败两种均成立）+ 遮罩点击关闭
const d03c = await Eval(`(async () => {
  document.querySelector(${JSON.stringify(detailSel)}).click();
  await new Promise((r) => setTimeout(r, 400));
  const ov = document.querySelector('.ref-files-overlay');
  const btn = ov.querySelector('[data-pdf-copy]');
  if (!btn) return { noBtn: true };
  btn.click();
  await new Promise((r) => setTimeout(r, 400));
  const msg = ov.querySelector('.pdf-detail-copy-msg').textContent;
  ov.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 250));
  return { msg, closedByMask: document.querySelectorAll('.ref-files-overlay').length === 0 };
})()`);
check("复制相对路径触发反馈（已复制 / 降级提示）",
  !d03c.noBtn && (d03c.msg === "已复制相对路径" || d03c.msg === "复制失败，请手动复制"), d03c.msg);
check("遮罩点击关闭弹窗", !!d03c.closedByMask);

// 0 字节损坏文件三态（临时注入 zz-smoke-broken.pdf，自建自清）+ Esc 关闭
const smokeBatch = await Eval(`window.__probe.pdfs[0].batch`);
const brokenRel = smokeBatch + "/zz-smoke-broken.pdf";
const brokenAbs = join(MATERIALS, smokeBatch, "zz-smoke-broken.pdf");
let brokenCreated = false;
try {
  writeFileSync(brokenAbs, "");
  brokenCreated = true;
  const d03b = await Eval(`(async () => {
    await window.__probe.reload();
    await new Promise((r) => setTimeout(r, 250));
    const btn = document.querySelector('#pdf-rows [data-pdf-detail="${brokenRel}"]');
    if (!btn) return { found: false, rows: document.querySelectorAll('#pdf-rows tr').length };
    btn.click();
    for (let i = 0; i < 30; i++) {
      await new Promise((r) => setTimeout(r, 200));
      const t = document.querySelector('.ref-files-overlay [data-pdf-pages]')?.textContent || '';
      if (t && !t.includes('读取中')) break;
    }
    const ov = document.querySelector('.ref-files-overlay');
    const out = { found: true,
      pagesText: ov.querySelector('[data-pdf-pages]')?.textContent || '',
      brokenBadge: !!ov.querySelector('.badge.pdf-broken'),
      rows: document.querySelectorAll('#pdf-rows tr').length,
      listHasIt: window.__probe.pdfs.some((p) => p.rel_path === "${brokenRel}") };
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await new Promise((r) => setTimeout(r, 250));
    out.closedByEsc = document.querySelectorAll('.ref-files-overlay').length === 0;
    return out;
  })()`);
  check("0 字节损坏文件进清单（列表实况 + 行数 = 全量 + 1）",
    d03b.found && d03b.listHasIt && d03b.rows === total + 1, `rows=${d03b.rows}`);
  check("损坏文件详情 = 「无法读取」三态 + ⚠ 损坏徽章",
    d03b.pagesText.includes("无法读取") && d03b.brokenBadge, d03b.pagesText);
  check("Esc 关闭详情弹窗", !!d03b.closedByEsc);
} finally {
  if (brokenCreated) { try { unlinkSync(brokenAbs); } catch {} }
  await Eval(`window.__probe.reload().catch(() => {})`);
  await sleep(500);
}

// ================= 工单 04：数据健康（疑似重复 / 损坏警示） =================
const d04 = await Eval(`(() => {
  const h = window.__probe.fx.pdfHealth(window.__probe.pdfs);
  const dupSeg = document.querySelector('#pdf-stats [data-pdf-health="dup"]');
  const brokenSeg = document.querySelector('#pdf-stats [data-pdf-health="broken"]');
  return {
    expDupGroups: h.dupGroups.length, expDupPaths: h.dupPaths.size, expBroken: h.broken.size,
    dupN: dupSeg ? Number((dupSeg.textContent.match(/(\\d+)/) || [])[1]) : 0,
    brokenSeg: !!brokenSeg,
    dupMarks: document.querySelectorAll('#pdf-rows .badge.pdf-dup').length,
    brokenMarks: document.querySelectorAll('#pdf-rows .badge.pdf-broken').length,
    rows: document.querySelectorAll('#pdf-rows tr').length,
  };
})()`);
check("重复红段 = 全量纯件口径（组数）", d04.dupN === d04.expDupGroups,
  `seg=${d04.dupN} exp=${d04.expDupGroups}`);
check("行内重复徽章数 = 纯件重复路径数", d04.dupMarks === d04.expDupPaths,
  `${d04.dupMarks} vs ${d04.expDupPaths}`);
check("损坏红段与行内徽章同纯件口径（无损坏 = 都不渲染）",
  d04.brokenSeg === (d04.expBroken > 0) && d04.brokenMarks === d04.expBroken,
  `expBroken=${d04.expBroken} seg=${d04.brokenSeg} marks=${d04.brokenMarks}`);

// 红段点击过滤（只显示重复类，与 q / 批次正交）→ 再点取消
if (d04.expDupGroups > 0) {
  const d04f = await Eval(`(async () => {
    document.querySelector('#pdf-stats [data-pdf-health="dup"]').click();
    await new Promise((r) => setTimeout(r, 300));
    const out = {
      rows: document.querySelectorAll('#pdf-rows tr').length,
      marks: document.querySelectorAll('#pdf-rows .badge.pdf-dup').length,
      on: !!(document.querySelector('#pdf-stats [data-pdf-health="dup"]') || {}).classList?.contains('on'),
      statsText: document.querySelector('#pdf-stats').textContent,
    };
    document.querySelector('#pdf-stats [data-pdf-health="dup"]').click();
    await new Promise((r) => setTimeout(r, 300));
    out.restored = document.querySelectorAll('#pdf-rows tr').length;
    return out;
  })()`);
  check("红段点击过滤：只显示重复类（行数 = 徽章数 = 纯件重复路径数）",
    d04f.rows === d04f.marks && d04f.rows === d04.expDupPaths && d04f.on,
    `rows=${d04f.rows} marks=${d04f.marks} exp=${d04.expDupPaths}`);
  check("统计条随 health 过滤收缩（共 N 份 = 行数）",
    d04f.statsText.includes(`共 ${d04f.rows} 份`), d04f.statsText.trim().slice(0, 40));
  check("红段再点取消恢复全量", d04f.restored === d04.rows, `${d04f.restored} vs ${d04.rows}`);
} else {
  check("红段过滤（库无重复，跳过）", true);
}

// 损坏双态：临时注入 0 字节 → 红段「损坏 1 份」+ 行内 1 个徽章 + 点击只显示 1 行 → 清理
let injected = false;
try {
  writeFileSync(brokenAbs, "");
  injected = true;
  const d04b = await Eval(`(async () => {
    await window.__probe.reload();
    await new Promise((r) => setTimeout(r, 250));
    const seg = document.querySelector('#pdf-stats [data-pdf-health="broken"]');
    const segText = seg ? seg.textContent : '';
    const marks = document.querySelectorAll('#pdf-rows .badge.pdf-broken').length;
    const dupMarks = document.querySelectorAll('#pdf-rows .badge.pdf-dup').length;
    if (!seg) return { segText, marks, dupMarks };
    seg.click();
    await new Promise((r) => setTimeout(r, 300));
    const out = { segText, marks, dupMarks, rows: document.querySelectorAll('#pdf-rows tr').length };
    document.querySelector('#pdf-stats [data-pdf-health="broken"]').click();
    await new Promise((r) => setTimeout(r, 300));
    return out;
  })()`);
  check("临时损坏注入 → 红段「损坏 1 份」", String(d04b.segText).includes("损坏 1 份"), d04b.segText);
  check("临时损坏注入 → 行内 ⚠ 损坏徽章恰好 1 个", d04b.marks === 1, "marks=" + d04b.marks);
  check("损坏红段点击：只显示损坏 1 行；重复徽章仍为全量",
    d04b.rows === 1 && d04b.dupMarks === d04.expDupPaths, `rows=${d04b.rows} dupMarks=${d04b.dupMarks}`);
} finally {
  if (injected) { try { unlinkSync(brokenAbs); } catch {} }
  await Eval(`window.__probe.reload().catch(() => {})`);
  await sleep(500);
  check("清理后损坏红段消失（回真实全量）",
    await Eval(`!document.querySelector('#pdf-stats [data-pdf-health="broken"]')
      && document.querySelectorAll('#pdf-rows tr').length === ${total}`));
}

// ================= 工单 05：空态（过滤无结果）+ 清空恢复 =================
const d05 = await Eval(`(async () => {
  const input = document.getElementById('pdf-filter');
  input.value = 'zz-绝对不存在的关键字-zz';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 450));
  const empty = document.querySelector('#pdf-rows .empty-state');
  const out = { hasEmpty: !!empty,
    text: (empty?.querySelector('.es-title') || {}).textContent || '',
    hint: (empty?.querySelector('.es-hint') || {}).textContent || '' };
  document.getElementById('pdf-filter-clear').click();
  await new Promise((r) => setTimeout(r, 300));
  out.restored = document.querySelectorAll('#pdf-rows tr').length;
  return out;
})()`);
check("过滤无结果空态（🔍 文案「没有匹配的 PDF 文件」+ 指向清空过滤）",
  d05.hasEmpty && d05.text.includes("没有匹配的 PDF 文件") && d05.hint.includes("清空过滤"), d05.text);
check("空态清空后恢复全量", d05.restored === total, `${d05.restored} vs ${total}`);

// ================= 工单 06：疑似重复回收删除（单删 + 组级，零真实素材触碰） =================
const dupRel1 = smokeBatch + "/zz-smoke-dup/zz-smoke-pair.pdf";
const dupRel2 = smokeBatch + "/zz-smoke-dup-2/zz-smoke-pair.pdf";
const dupRel3 = smokeBatch + "/zz-smoke-dup-3/zz-smoke-pair.pdf";
const dupBytes = "%PDF-1.4\nzz smoke pair（pdf-library-ui/06 冒烟合成对）";
const dupAbs = [dupRel1, dupRel2, dupRel3].map((r) => join(MATERIALS, r));
const dupDirs = [
  join(MATERIALS, smokeBatch, "zz-smoke-dup"), join(MATERIALS, smokeBatch, "zz-smoke-dup-2"),
  join(MATERIALS, smokeBatch, "zz-smoke-dup-3"),
  join(TRASH, dateStr, smokeBatch, "zz-smoke-dup"), join(TRASH, dateStr, smokeBatch, "zz-smoke-dup-2"),
  join(TRASH, dateStr, smokeBatch, "zz-smoke-dup-3"),
];
let dupCreated = false;
try {
  mkdirSync(join(MATERIALS, smokeBatch, "zz-smoke-dup"), { recursive: true });
  mkdirSync(join(MATERIALS, smokeBatch, "zz-smoke-dup-2"), { recursive: true });
  writeFileSync(dupAbs[0], dupBytes);
  writeFileSync(dupAbs[1], dupBytes);
  dupCreated = true;

  const d06a = await Eval(`(async () => {
    await window.__probe.reload();
    await new Promise((r) => setTimeout(r, 250));
    // 弹窗等待（第十轮修）：打开删除确认前先 \`await apiGet(pdfRefsUrl(rel_path))\`
    // （ui/pdf.js openPdfTrashConfirm）——本机 webapp 实测该请求 ≈500ms
    // （/api/pdfs 500ms 量级，见 .scratch/pdf-library-ui/diag-refs-timing.mjs），
    // 弹窗首现 ≈518ms（diag-trash-modal-flake.mjs）。旧写法 \`sleep(400)\` 后直接读
    // overlay → 确定性 null（本批复跑两轮都红）。改为**轮询等到场**（最长 5s），
    // 与脚本其它处 waitFor 姿势一致。
    const waitOverlay = async (ms = 5000) => {
      for (let i = 0; i < ms / 50; i++) {
        const o = document.querySelector('.ref-files-overlay');
        if (o) return o;
        await new Promise((r) => setTimeout(r, 50));
      }
      return null;
    };
    const pairDup = () => [...document.querySelectorAll('#pdf-rows tr')]
      .filter((tr) => tr.querySelector('[data-pdf-trash="${dupRel1}"]')
        || tr.querySelector('[data-pdf-trash="${dupRel2}"]'))
      .filter((tr) => tr.querySelector('.badge.pdf-dup')).length;
    const before = pairDup();
    if (!document.querySelector('#pdf-rows [data-pdf-trash="${dupRel1}"]')) {
      return { found: false, before };
    }
    document.querySelector('#pdf-rows [data-pdf-trash="${dupRel1}"]').click();
    const ov = await waitOverlay();
    if (!ov) return { found: true, before, overlayMissing: true };   // 显式失败（不再抛 null 崩脚本）
    const out = {
      found: true, before, text: ov.textContent,
      hasModal: !!ov.querySelector('.confirm-modal'),
      hasCancel: !!ov.querySelector('[data-confirm-cancel]'),
      hasOk: !!ov.querySelector('[data-confirm-ok]'),
      okText: ov.querySelector('[data-confirm-ok]').textContent,
    };
    ov.querySelector('[data-confirm-cancel]').click();
    await new Promise((r) => setTimeout(r, 300));
    out.cancelled = document.querySelectorAll('.ref-files-overlay').length === 0;
    out.stillHas1 = !!document.querySelector('#pdf-rows [data-pdf-trash="${dupRel1}"]');
    document.querySelector('#pdf-rows [data-pdf-trash="${dupRel1}"]').click();
    await waitOverlay();                                            // 同上：等弹窗到场再点确认
    document.querySelector('.ref-files-overlay [data-confirm-ok]').click();
    for (let i = 0; i < 60; i++) {
      await new Promise((r) => setTimeout(r, 200));
      const t = [...document.querySelectorAll('.toast .toast-text')].map((x) => x.textContent).join('|');
      if (t.includes('已移入回收目录')) out.toast = t;
      if (!document.querySelector('#pdf-rows [data-pdf-trash="${dupRel1}"]')) break;
    }
    out.toast = out.toast || '';
    out.after = pairDup();
    // 清单实况：重新拉一次（确认弹窗内部走 ui 模块自己的 loadPdfs，探针缓存需自刷新）
    await window.__probe.reload();
    out.rows = document.querySelectorAll('#pdf-rows tr').length;
    out.listHas1 = window.__probe.pdfs.some((p) => p.rel_path === "${dupRel1}");
    out.listHas2 = window.__probe.pdfs.some((p) => p.rel_path === "${dupRel2}");
    return out;
  })()`);
  check("自配套：合成对进重复组（2 行带重复徽章）", d06a.found && d06a.before === 2, `dupBaseline=${d06a.before}`);
  check("确认弹窗：共享工厂 + 路径 / 大小 / 回收去向 / 参考镜像提示 + 双钮",
    d06a.hasModal && d06a.text.includes(dupRel1) && d06a.text.includes("大小")
      && d06a.text.includes("回收去向") && d06a.text.includes("参考库条目引用")
      && d06a.text.includes("git 已忽略") && d06a.hasCancel && d06a.hasOk
      && d06a.okText.trim() === "确认删除",
    String(d06a.okText).trim());
  check("取消：弹窗关闭且文件未删（目标行删除按钮仍在）",
    d06a.cancelled && d06a.stillHas1, `stillHas1=${d06a.stillHas1}`);
  check("确认单删：toast「已移入回收目录」+ 该行消失 + 清单不再含它 + 余单份不再成组",
    d06a.toast.includes("已移入回收目录") && d06a.listHas1 === false && d06a.listHas2 === true
      && d06a.after === 0 && d06a.rows === total + 1,
    `toast=${d06a.toast} after=${d06a.after} rows=${d06a.rows}`);
  check("trash 落盘：镜像内容与源一致",
    existsSync(join(TRASH, dateStr, dupRel1))
      && readFileSync(join(TRASH, dateStr, dupRel1), "utf8") === dupBytes, dateStr + "/" + dupRel1);
  check("源文件已移走（磁盘实况）", !existsSync(dupAbs[0]));

  // 组级「保留此文件，删除其余 1 份」：再注入第三份合成新对（dupRel2 + dupRel3）
  mkdirSync(join(MATERIALS, smokeBatch, "zz-smoke-dup-3"), { recursive: true });
  writeFileSync(dupAbs[2], dupBytes);
  const d06b = await Eval(`(async () => {
    // 弹窗等待与 d06a 同口径：详情弹窗 / 确认弹窗都在一次慢请求之后才出现
    // （本机 webapp 端点 ≈500ms 量级），固定 sleep 会抢跑 → 轮询等到场。
    const waitOverlay = async (ms = 5000) => {
      for (let i = 0; i < ms / 50; i++) {
        const o = document.querySelector('.ref-files-overlay');
        if (o) return o;
        await new Promise((r) => setTimeout(r, 50));
      }
      return null;
    };
    const waitConfirm = async (ms = 5000) => {
      for (let i = 0; i < ms / 50; i++) {
        const o = [...document.querySelectorAll('.ref-files-overlay')]
          .find((x) => x.querySelector('[data-confirm-ok]'));
        if (o) return o;
        await new Promise((r) => setTimeout(r, 50));
      }
      return null;
    };
    await window.__probe.reload();
    await new Promise((r) => setTimeout(r, 250));
    document.querySelector('#pdf-rows [data-pdf-detail="${dupRel2}"]').click();
    const det = await waitOverlay();
    if (!det) return { found: false, overlayMissing: true };
    const groupBtn = await (async () => {
      for (let i = 0; i < 100; i++) {
        const b = det.querySelector('[data-pdf-delete-group]');
        if (b) return b;
        await new Promise((r) => setTimeout(r, 50));
      }
      return null;
    })();
    if (!groupBtn) return { found: false };
    const out = { found: true, groupText: groupBtn.textContent.trim() };
    groupBtn.click();
    const ov = await waitConfirm();
    if (!ov) return { found: false, overlayMissing: true };
    out.overlayCount = document.querySelectorAll('.ref-files-overlay').length;
    out.title = ov.querySelector('.ref-files-head strong').textContent;
    out.members = ov.querySelectorAll('.pdf-trash-members li').length;
    out.memberText = (ov.querySelector('.pdf-trash-members') || {}).textContent || '';
    ov.querySelector('[data-confirm-ok]').click();
    for (let i = 0; i < 60; i++) {
      await new Promise((r) => setTimeout(r, 200));
      if (!document.querySelector('#pdf-rows [data-pdf-detail="${dupRel3}"]')) break;
    }
    await window.__probe.reload();
    out.rows = document.querySelectorAll('#pdf-rows tr').length;
    out.listHas2 = window.__probe.pdfs.some((p) => p.rel_path === "${dupRel2}");
    out.listHas3 = window.__probe.pdfs.some((p) => p.rel_path === "${dupRel3}");
    return out;
  })()`);
  check("组级按钮文案 = 保留此文件，删除其余 1 份",
    d06b.found && String(d06b.groupText).includes("删除其余 1 份"), d06b.groupText);
  check("组级确认弹窗：成员清单 2 项（含保留与删除对象）+ 标题「保留一份删其余」",
    d06b.members === 2 && String(d06b.memberText).includes(dupRel2)
      && String(d06b.memberText).includes(dupRel3) && String(d06b.title).includes("保留一份删其余"),
    `members=${d06b.members} title=${d06b.title}`);
  check("组级确认后：保留对象仍在清单、其余成员已回收、余 N 份不再成组",
    d06b.listHas2 === true && d06b.listHas3 === false && d06b.rows === total + 1,
    `rows=${d06b.rows}（全量 ${total} + 保留的 dupRel2）`);
  check("组级回收落盘（镜像内容一致）", existsSync(join(TRASH, dateStr, dupRel3))
    && readFileSync(join(TRASH, dateStr, dupRel3), "utf8") === dupBytes, dateStr + "/" + dupRel3);
} finally {
  if (dupCreated) {
    for (const p of dupAbs) { try { unlinkSync(p); } catch {} }
    for (const d of dupDirs) { try { rmSync(d, { recursive: true, force: true }); } catch {} }
    await Eval(`window.__probe.reload().catch(() => {})`);
    await sleep(500);
    const clean = await Eval(`(() => ({
      pair: window.__probe.pdfs.filter((p) => p.name === 'zz-smoke-pair.pdf').length,
      rows: document.querySelectorAll('#pdf-rows tr').length }))()`);
    check("清理后回到真实全量（无 zz-smoke 痕迹，回收镜像亦清除）",
      clean.pair === 0 && clean.rows === total, `pair=${clean.pair} rows=${clean.rows}`);
  }
}

// ================= 截图存档（工单 05 目视验收产物） =================
mkdirSync(join(ROOT, ".scratch", "pdf-library-ui"), { recursive: true });
await Eval(`document.getElementById('tab-pdf').scrollIntoView({ block: 'start' })`);
await sleep(400);
const shotFull = await c.cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(join(ROOT, ".scratch", "pdf-library-ui", "shot-05-full.png"),
  Buffer.from(shotFull.result.data, "base64"));
const shotDup = await Eval(`(async () => {
  const seg = document.querySelector('#pdf-stats [data-pdf-health="dup"]');
  if (!seg) return false;
  seg.click();
  await new Promise((r) => setTimeout(r, 350));
  return document.querySelectorAll('#pdf-rows tr').length;
})()`);
if (shotDup) {
  const s2 = await c.cdp("Page.captureScreenshot", { format: "png" });
  writeFileSync(join(ROOT, ".scratch", "pdf-library-ui", "shot-05-dup-filtered.png"),
    Buffer.from(s2.result.data, "base64"));
  await Eval(`document.querySelector('#pdf-stats [data-pdf-health="dup"]').click()`);
  await sleep(300);
}
const shotDetail = await Eval(`(async () => {
  document.querySelector('#pdf-rows [data-pdf-detail]').click();
  for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 200));
    const t = document.querySelector('.ref-files-overlay [data-pdf-pages]')?.textContent || '';
    if (t && !t.includes('读取中')) break;
  }
  return !!document.querySelector('.ref-files-overlay');
})()`);
if (shotDetail) {
  const s3 = await c.cdp("Page.captureScreenshot", { format: "png" });
  writeFileSync(join(ROOT, ".scratch", "pdf-library-ui", "shot-05-detail.png"),
    Buffer.from(s3.result.data, "base64"));
  await Eval(`document.querySelector('.ref-files-overlay .ref-files-close')?.click()`);
}
console.log("shot-05-full / shot-05-dup-filtered / shot-05-detail 已存档");

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
c.close();
process.exit(failed === 0 ? 0 : 1);
