// 冒烟（pdf-library-ui 系列）：PDF 资料库页 UI。每张工单追加检查项。
// 零依赖：node 内置 fetch + WebSocket 直连 Chrome CDP（9251）；webapp 8000 提供真实 /api/pdfs。
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
      && !!document.getElementById('tab-pdf')
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

// ---- 切「PDF 资料库」tab ----
await Eval(`(() => {
  const tab = [...document.querySelectorAll('nav button')]
    .find((b) => b.textContent.trim() === 'PDF 资料库');
  if (tab) tab.click();
  return !!tab;
})()`);
for (let i = 0; i < 40; i++) {
  const n = await Eval(`(pdfCache || []).length`);
  if (n > 0) break;
  await new Promise((r) => setTimeout(r, 250));
}

const loaded = await Eval(`(pdfCache || []).length`);
check("PDF 列表已加载（pdfCache 非空）", loaded > 0, "pdfs=" + loaded);

// ================= 工单 02：表格精修 + 客户端即时检索 + 统计条 =================
check("旧筛选区已移除（无搜索/清空按钮、无计数 span、无 pdf-count）", await Eval(`!document.getElementById('btn-pdf-search')
  && !document.getElementById('btn-pdf-search-clear') && !document.getElementById('pdf-count')`));

check("工具栏元素齐全（搜索 / 排序 / 方向 / 清空 / 批次 chips / 统计条）", await Eval(`!!(document.getElementById('pdf-filter')
  && document.getElementById('pdf-sort') && document.getElementById('pdf-sort-dir')
  && document.getElementById('pdf-filter-clear') && document.getElementById('pdf-batch-chips')
  && document.getElementById('pdf-stats'))`));

// 防 id 冲突回归（对偶 reference 评审 C1）：pdf- 前缀元素 id 全局唯一
check("pdf- 前缀元素 id 唯一（无重复 id）", await Eval(`(() => {
  const ids = [...document.querySelectorAll('[id^="pdf-"]')].map((i) => i.id);
  return ids.length === new Set(ids).size && ids.length >= 10;
})()`));

const t02c = await Eval(`(() => {
  const table = document.querySelector('#tab-pdf table');
  const th = document.querySelector('#tab-pdf thead th');
  const ths = [...document.querySelectorAll('#tab-pdf thead th')].map((t) => t.textContent.trim());
  return { hasLibTable: !!(table && table.classList.contains('lib-table')),
    thBg: th ? getComputedStyle(th).backgroundColor : null,
    ths, rows: document.querySelectorAll('#pdf-rows tr').length };
})()`);
check("表格带 lib-table 类", t02c.hasLibTable);
check("表头有底纹背景", !!t02c.thBg && t02c.thBg !== "rgba(0, 0, 0, 0)", "bg=" + t02c.thBg);
check("表头 6 列（文件名/批次/目录/大小/修改时间/操作）",
  JSON.stringify(t02c.ths) === JSON.stringify(["文件名", "批次", "目录", "大小", "修改时间", "操作"]),
  t02c.ths.join("/"));
check("行数 = 全量份数", t02c.rows === loaded, `rows=${t02c.rows}, pdfs=${loaded}`);

const t02e = await Eval(`(() => {
  const first = document.querySelector('#pdf-rows tr');
  if (!first) return null;
  const nameTd = first.querySelector('.desc-cell');
  const chip = first.querySelector('.lib-chip');
  const tds = [...first.querySelectorAll('td')];
  const btnOpen = first.querySelector('[data-open-pdf]');
  const btnDetail = first.querySelector('[data-pdf-detail]');
  return { nameTitle: nameTd ? (nameTd.title || '') : '', chipText: chip ? chip.textContent.trim() : null,
    tds: tds.map((td) => td.textContent.trim()),
    btnOpenText: first.querySelector('button[data-open-pdf]')?.textContent.trim() ?? null,
    btnDetailText: btnDetail ? btnDetail.textContent.trim() : null };
})()`);
check("首行文件名列 = 截断类 + 完整路径 tooltip", !!(t02e && t02e.nameTitle && t02e.nameTitle.includes('/')), t02e && t02e.nameTitle);
check("首行批次 chip（.lib-chip 文案）", !!(t02e && t02e.chipText), t02e && t02e.chipText);
check("首行大小列 = formatSize 口径", await Eval(`(() => {
  const first = document.querySelector('#pdf-rows tr');
  if (!first) return false;
  const sorted = pdfSortEntries(pdfCache, { by: 'name', dir: 'asc' });
  const sizeTd = [...first.querySelectorAll('td')][3];
  return sizeTd && sizeTd.textContent.trim() === formatSize(sorted[0].size_bytes);
})()`));
check("首行修改时间列含 YYYY-MM-DD", await Eval(`(() => {
  const first = document.querySelector('#pdf-rows tr');
  if (!first) return false;
  const mtTd = [...first.querySelectorAll('td')][4];
  return mtTd && /^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}$/.test(mtTd.textContent.trim());
})()`));
check("操作列：打开 + 详情按钮", !!(t02e && t02e.btnOpenText === "打开" && t02e.btnDetailText === "详情"));

// ---- 统计条（无过滤时 = 全量口径）----
check("统计条文案 = pdfStatsText(pdfStats(全量))", await Eval(`(() => {
  const text = document.getElementById('pdf-stats').textContent;
  const expected = pdfStatsText(pdfStats(pdfFilterEntries(pdfCache, pdfFilterContext())));
  return text.includes(expected);
})()`));

// ---- 关键字即时过滤（防抖 150ms）----
const kwRows = await Eval(`(async () => {
  const inp = document.getElementById('pdf-filter');
  inp.value = '数据手册';
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 400));
  return document.querySelectorAll('#pdf-rows tr').length;
})()`);
check("关键字即时过滤：命中数 > 0 且 < 全量", kwRows > 0 && kwRows < loaded, "rows=" + kwRows);

// ---- 批次 chips：点击过滤 / 再点取消 ----
const chipTest = await Eval(`(async () => {
  document.getElementById('pdf-filter-clear').click(); // 清掉前面遗留的关键字过滤
  await new Promise((r) => setTimeout(r, 120));
  const btn = [...document.querySelectorAll('#pdf-batch-chips [data-pdf-chip]')]
    .find((b) => b.dataset.pdfChip !== '');
  if (!btn) return null;
  const batch = btn.dataset.pdfChip;
  btn.click();
  await new Promise((r) => setTimeout(r, 120));
  const filtered = document.querySelectorAll('#pdf-rows tr').length;
  const expected = (pdfCache || []).filter((p) => p.batch === batch).length;
  // chips 重渲染后旧引用已脱离文档：重新按 value 查找再点（取消）
  const btn2 = [...document.querySelectorAll('#pdf-batch-chips [data-pdf-chip]')]
    .find((b) => b.dataset.pdfChip === batch);
  if (btn2) btn2.click();
  await new Promise((r) => setTimeout(r, 120));
  const restored = document.querySelectorAll('#pdf-rows tr').length;
  return { batch, filtered, expected, restored, full: (pdfCache || []).length };
})()`);
check("批次 chip 点击 = 只看该批次（行数 = 该批次份数）", !!(chipTest && chipTest.filtered === chipTest.expected && chipTest.filtered > 0),
  chipTest && `${chipTest.batch}: ${chipTest.filtered}/${chipTest.expected}`);
check("批次 chip 再点取消 = 恢复全量", !!(chipTest && chipTest.restored === chipTest.full), chipTest && "rows=" + chipTest.restored);

// ---- 排序切换：按大小降序 → 首行最大 ----
const sortTest = await Eval(`(async () => {
  const sel = document.getElementById('pdf-sort');
  sel.value = 'size';
  sel.dispatchEvent(new Event('change', { bubbles: true }));
  document.getElementById('pdf-sort-dir').click(); // asc → desc
  await new Promise((r) => setTimeout(r, 120));
  const firstRow = document.querySelector('#pdf-rows tr');
  if (!firstRow) return null;
  const sizeTd = [...firstRow.querySelectorAll('td')][3];
  return { top: sizeTd.textContent.trim(), max: formatSize(Math.max(...pdfCache.map((p) => p.size_bytes))) };
})()`);
check("排序切换：按大小降序首行 = 最大文件", !!(sortTest && sortTest.top === sortTest.max), sortTest && `${sortTest.top} vs ${sortTest.max}`);

// ---- 清空过滤：恢复全量 ----
check("清空过滤恢复全量", await Eval(`(async () => {
  document.getElementById('pdf-filter-clear').click();
  await new Promise((r) => setTimeout(r, 120));
  return document.querySelectorAll('#pdf-rows tr').length === (pdfCache || []).length;
})()`));

// ================= 工单 03：轻量详情弹窗（页数懒取 + 复制相对路径） =================
const d03 = await Eval(`(async () => {
  const pdf = (pdfCache || []).find((p) => p.name === 'TB6612FNG电机驱动芯片数据手册.pdf')
    || (pdfCache || [])[0];
  if (!pdf) return null;
  const btn = [...document.querySelectorAll('#pdf-rows tr [data-pdf-detail]')]
    .find((b) => b.dataset.pdfDetail === pdf.rel_path);
  if (!btn) return null;
  btn.click();
  await new Promise((r) => setTimeout(r, 800)); // 页数懒取
  const overlay = document.querySelector('.ref-files-overlay');
  if (!overlay) return { open: false };
  const text = overlay.textContent;
  const pagesText = overlay.querySelector('[data-pdf-pages]')?.textContent || '';
  const hasCopyMsg = !!overlay.querySelector('.pdf-detail-copy-msg');
  overlay.querySelector('.ref-files-close').click(); // × 关闭
  await new Promise((r) => setTimeout(r, 100));
  const closedByX = !document.querySelector('.ref-files-overlay');
  return { open: true, hasPath: text.includes(pdf.rel_path), pagesText, hasCopyMsg, closedByX, name: pdf.name };
})()`);
check("详情弹窗打开（行「详情」→ 遮罩弹窗）", !!(d03 && d03.open), d03 && d03.name);
check("详情含完整相对路径", !!(d03 && d03.hasPath));
check("页数懒取：真实文件成功显示 N 页",
  !!(d03 && d03.pagesText.includes("页") && !d03.pagesText.includes("无法读取") && !d03.pagesText.includes("读取中")),
  d03 && d03.pagesText);
check("操作区含复制按钮消息槽", !!(d03 && d03.hasCopyMsg));
check("× 关闭弹窗", !!(d03 && d03.closedByX));

// 损坏三态验证：素材库现无 0 字节文件（历史 3 份均已修复为真 PDF），
// 临时创建 0 字节文件走真实链路（写入/清理由本脚本负责，不留痕迹）。
import { writeFileSync, unlinkSync } from "node:fs";
import { resolve } from "node:path";
const smokeBatch = await Eval(`(pdfCache[0] || {}).batch`);
const brokenRel = smokeBatch + "/zz-smoke-broken.pdf";
const brokenAbs = resolve("sources/materials", brokenRel);
let brokenCreated = false;
try {
  if (smokeBatch) { // 空防御：库为空（无批次）时跳过损坏专测，不写盘
    writeFileSync(brokenAbs, "");
    brokenCreated = true;
    const d03b = await Eval(`(async () => {
      await loadPdfs(); // 重拉全量（含临时损坏文件）
      await new Promise((r) => setTimeout(r, 300));
      const pdf = (pdfCache || []).find((p) => p.name === 'zz-smoke-broken.pdf');
      if (!pdf) return { found: false };
      const btn = [...document.querySelectorAll('#pdf-rows tr [data-pdf-detail]')]
        .find((b) => b.dataset.pdfDetail === pdf.rel_path);
      if (!btn) return { found: false };
      btn.click();
      await new Promise((r) => setTimeout(r, 800));
      const overlay = document.querySelector('.ref-files-overlay');
      const pagesText = overlay?.querySelector('[data-pdf-pages]')?.textContent || '';
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      await new Promise((r) => setTimeout(r, 100));
      const closedByEsc = !document.querySelector('.ref-files-overlay');
      return { found: true, pagesText, closedByEsc };
    })()`);
    check("0 字节损坏文件详情 → 无法读取三态", !!(d03b && d03b.found && d03b.pagesText.includes("无法读取")), d03b && d03b.pagesText);
    check("Esc 关闭弹窗", !!(d03b && d03b.closedByEsc));
    const d03b2 = await Eval(`(async () => {
      const pdf = (pdfCache || []).find((p) => p.name === 'zz-smoke-broken.pdf');
      if (!pdf) return null;
      const btn = [...document.querySelectorAll('#pdf-rows tr [data-pdf-detail]')]
        .find((b) => b.dataset.pdfDetail === pdf.rel_path);
      if (!btn) return null;
      btn.click();
      await new Promise((r) => setTimeout(r, 150));
      const overlay = document.querySelector('.ref-files-overlay');
      if (!overlay) return null;
      overlay.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      await new Promise((r) => setTimeout(r, 100));
      return { closed: !document.querySelector('.ref-files-overlay') };
    })()`);
    check("遮罩点击关闭弹窗", !!(d03b2 && d03b2.closed));
  }
} finally {
  if (brokenCreated) { try { unlinkSync(brokenAbs); } catch {} }
  await Eval(`loadPdfs().catch(() => {})`); // 清理后列表即时回到真实全量
}

const d03c = await Eval(`(async () => {
  const pdf = (pdfCache || [])[0];
  if (!pdf) return null;
  const btn = [...document.querySelectorAll('#pdf-rows tr [data-pdf-detail]')]
    .find((b) => b.dataset.pdfDetail === pdf.rel_path);
  if (!btn) return null;
  btn.click();
  await new Promise((r) => setTimeout(r, 300));
  const overlay = document.querySelector('.ref-files-overlay');
  const copyBtn = overlay?.querySelector('[data-pdf-copy]');
  if (!overlay || !copyBtn) return null;
  copyBtn.click();
  await new Promise((r) => setTimeout(r, 400));
  const msg = overlay.querySelector('.pdf-detail-copy-msg')?.textContent || '';
  overlay.querySelector('.ref-files-close').click();
  return { msg };
})()`);
check("复制相对路径触发反馈（已复制或降级失败提示）",
  !!(d03c && (d03c.msg === "已复制相对路径" || d03c.msg === "复制失败，请手动复制")), d03c && d03c.msg);

// ================= 工单 04：数据健康（重复 / 损坏警示） =================
// 现状修订基线：4 组疑似重复（000_2017-2025 两批各一 + 塔克R3 三份芯片手册
// 各两组）、0 字节损坏 0 份。断言按「≥ 下限 + 双态」设计——素材库增删数字
// 变化只影响下限与双态注入，判据不变。
const d04 = await Eval(`(async () => {
  const stats = document.querySelector('#pdf-stats');
  if (!stats) return null;
  const text = stats.textContent || '';
  const dupSeg = [...stats.querySelectorAll('[data-pdf-health="dup"]')][0];
  const dupN = dupSeg ? Number((dupSeg.textContent.match(/(\\d+)/) || [])[1]) : 0;
  const brokenSeg = stats.querySelector('[data-pdf-health="broken"]');
  const dupMarks = document.querySelectorAll('#pdf-rows .badge.pdf-dup').length;
  const brokenMarks = document.querySelectorAll('#pdf-rows .badge.pdf-broken').length;
  return { text, dupN, brokenSeg: !!brokenSeg, brokenText: brokenSeg ? brokenSeg.textContent : "",
           dupMarks, brokenMarks, rows: document.querySelectorAll('#pdf-rows tr').length };
})()`);
check("健康红段：疑似重复 ≥ 4 组（全量口径真值）", !!(d04 && d04.dupN >= 4), d04 && `dup=${d04.dupN}`);
check("行内重复徽章 ≥ 8 个（4 组 × 2 成员下限）", !!(d04 && d04.dupMarks >= 8), d04 && `marks=${d04.dupMarks}`);
check("现状无损坏：损坏红段不显示 / 无行内损坏徽章",
  !!(d04 && !d04.brokenSeg && d04.brokenMarks === 0));

const d04f = await Eval(`(async () => {
  const seg = document.querySelector('[data-pdf-health="dup"]');
  if (!seg) return null;
  seg.click(); // 点击 = 只看重复类（innerHTML 重渲染后旧 span 已分离，
               // 每次操作都重新 query——detached 元素 click 不冒泡到容器）
  await new Promise((r) => setTimeout(r, 100));
  const rows = document.querySelectorAll('#pdf-rows tr').length;
  const marks = document.querySelectorAll('#pdf-rows .badge.pdf-dup').length;
  const statsText = (document.querySelector('#pdf-stats') || {}).textContent || '';
  const on = !!(document.querySelector('[data-pdf-health="dup"]') || {}).classList?.contains('on');
  document.querySelector('[data-pdf-health="dup"]').click(); // 再点取消（新 span）
  await new Promise((r) => setTimeout(r, 100));
  const restored = document.querySelectorAll('#pdf-rows tr').length;
  return { rows, marks, on, restored, statsText };
})()`);
check("红段点击过滤：只显示重复类（行数 = 徽章数，全是重复）",
  !!(d04f && d04f.rows >= 8 && d04f.rows === d04f.marks && d04f.rows === 2 * (d04 && d04.dupN)),
  d04f && `rows=${d04f.rows}`);
check("统计条随 health 过滤收缩（共 N 份 = 行数）",
  !!(d04f && d04f.statsText.includes(`共 ${d04f.rows} 份`)), d04f && d04f.statsText);
check("红段再点取消恢复全量", !!(d04f && d04f.on && d04f.restored === d04.rows));

// 损坏双态：临时注入 0 字节 → 红段「损坏 1 份」+ 行内徽章 + 点击只显示损坏 → 清理
let brokenInjected = false;
try {
  if (smokeBatch) {
    writeFileSync(brokenAbs, "");
    brokenInjected = true;
    const d04b = await Eval(`(async () => {
      await loadPdfs();
      await new Promise((r) => setTimeout(r, 300));
      const seg = document.querySelector('[data-pdf-health="broken"]');
      const segText = seg ? seg.textContent : '';
      const marks = document.querySelectorAll('#pdf-rows .badge.pdf-broken').length;
      const dupMarks = document.querySelectorAll('#pdf-rows .badge.pdf-dup').length;
      if (!seg) return { segText, marks, dupMarks };
      seg.click();
      await new Promise((r) => setTimeout(r, 100));
      const rows = document.querySelectorAll('#pdf-rows tr').length;
      document.querySelector('[data-pdf-health="broken"]').click(); // 还原（新 span）
      await new Promise((r) => setTimeout(r, 100));
      return { segText, marks, dupMarks, rows };
    })()`);
    check("临时损坏注入 → 红段「损坏 1 份」", !!(d04b && d04b.segText.includes("损坏 1 份")), d04b && d04b.segText);
    check("临时损坏注入 → 行内 ⚠ 损坏徽章恰好 1 个", !!(d04b && d04b.marks === 1), d04b && `marks=${d04b && d04b.marks}`);
    check("损坏红段点击：只显示损坏 1 行；重复徽章仍为全量 ≥ 8",
      !!(d04b && d04b.rows === 1 && d04b.dupMarks >= 8), d04b && `rows=${d04b && d04b.rows}`);
  }
} finally {
  if (brokenInjected) { try { unlinkSync(brokenAbs); } catch {} }
  await Eval(`loadPdfs().catch(() => {})`); // 清理后回到真实全量
  const d04c = await Eval(`(async () => {
    await new Promise((r) => setTimeout(r, 200));
    const seg = document.querySelector('[data-pdf-health="broken"]');
    return { hasBroken: !!seg, rows: document.querySelectorAll('#pdf-rows tr').length };
  })()`);
  check("清理后损坏红段消失（回真实全量）", !!(d04c && !d04c.hasBroken));
}

console.log(failed ? `\n冒烟结果：${failed} 项失败` : "\n冒烟结果：全部通过");
process.exit(failed ? 1 : 0);
