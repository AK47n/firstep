// ui/topic.js — 赛题库 tab + 拆条校对 DOM 胶水（阶段 2 工单 09）
//
// 赛题库 tab 全部胶水：历年真题汇总长 PDF 置顶链接（loadTopicArchiveLink——
// 工单 09 顺带修正 pdfFileUrl 单源：05 迁移后悬空，本模块与 ui/pdf.js 共用
// fx/pdf.js 的 pdfFileUrl）/ 年份 chips / 统计 / 卡片列表 / 详情弹窗（含页图
// 懒取 memo）/ 编辑弹窗 / 过滤 / 工具栏 / 功能组词表 / 删除 / 拆条校对表与
// 确认入库（btn-topic-split / btn-topic-confirm）。纯件在 fx/topic.js
// （16 函数——工单 04 迁）；题面载入事务 useTopic 归 ui/generate-recommend.js
// （工单 12），本模块「载入到生成页」按钮 import 调用。
// 状态（模块内）：topicRows / topicPdfFile / topicArchiveLoaded / topicUI /
// topicEntries / topicGroupVocab / topicSearchTimer / topicLoading /
// topicPageCache（页图 memo Map）。无跨簇 mutable 状态。
// host 页签分发器经顶部 import 调 loadTopics / loadTopicGroupVocabulary；
// initTopicToolbar 在模块顶部调用（import 时绑定，DOM 已就绪）。
import { $, apiGet, apiPut, apiDelete, toast, handle } from "/js/app.js";
import { confirmModal } from "/js/ui/confirm.js";
import { esc } from "/js/fx/core.js";
import { pdfFileUrl } from "/js/fx/pdf.js";
import { topicChipRowHTML, topicFilterEntries, topicSortEntries, topicStats, topicStatsText, topicCardHTML, topicDetailHTML, topicPagesHTML, topicPagesErrorHTML, topicEditHTML, topicEditValidate, topicEditPayload, topicGroupVocabulary } from "/js/fx/topic.js";
import { useTopic } from "/js/ui/generate-recommend.js";

let topicRows = [];      // 校对表草稿：[{year, number, problem_text}]
let topicPdfFile = null; // 待确认的原 PDF（确认时随 multipart 重新上传，AI 拆错可查原文）

// 历年真题汇总长 PDF（2017-2025）置顶链接：素材库同名定位（批次目录变动
// 也能命中），点击新标签浏览器原生预览；素材库缺失 / 未找到 = 不显示
let topicArchiveLoaded = false;
async function loadTopicArchiveLink() {
  if (topicArchiveLoaded) return;
  topicArchiveLoaded = true;
  const box = $("topic-archive-link");
  try {
    const pdfs = await apiGet("/api/pdfs?name=" + encodeURIComponent("000_2017-2025"));
    if (!pdfs.length) return;
    const p = pdfs[0];
    box.innerHTML = `<a href="#" data-open-archive-pdf title="${esc(p.rel_path)}">📄 历年真题汇总（2017-2025）长 PDF —— 点击打开</a>`;
    box.querySelector("[data-open-archive-pdf]").addEventListener("click", (e) => {
      e.preventDefault();
      window.open(pdfFileUrl(p.rel_path), "_blank"); // 浏览器原生 PDF 预览
    });
  } catch (e) { /* 素材库查询失败 = 不显示链接，不打扰浏览 */ }
}

// —— 赛题库工具栏状态与渲染（工单 topic-library-ui/03）：过滤条件集中于此，
// 事件层只转发；loadTopics 只负责拉数据入缓存，rendering 全走 renderTopics。
let topicUI = { q: "", year: "", sortBy: "key", sortDir: "asc", health: false };
let topicEntries = [];      // /api/topics 全量缓存（含 health 字段）
let topicGroupVocab = {};   // 功能组词表（/api/modules 派生，空 = hint 悬空降级）
let topicSearchTimer = null;
let topicLoading = false;   // 列表拉取中（加载态）

function topicFilterContext() {
  return {
    q: topicUI.q,
    year: topicUI.year,
    health: topicUI.health,
    groupIds: Object.keys(topicGroupVocab),
  };
}

function renderTopicYearChips() {
  const counts = {};
  for (const t of topicEntries) counts[t.year] = (counts[t.year] || 0) + 1;
  const options = [{ value: "", label: "全部", count: topicEntries.length }]
    .concat(Object.keys(counts).sort().map((y) => ({
      value: y, label: y, count: counts[y],
    })));
  $("topic-year-chips").innerHTML = topicChipRowHTML(options, topicUI.year);
}

function renderTopicStats() {
  const f = topicFilterContext();
  const filtered = topicFilterEntries(topicEntries, f);
  const stats = topicStats(filtered, f.groupIds);
  $("topic-stats").innerHTML = esc(topicStatsText(stats)) + (stats.issues
    ? ` <span class="lib-stats-red${topicUI.health ? " on" : ""}" data-topic-health title="原 PDF 缺失 / 附带程序悬空 / 功能组悬空的条目；点击只看问题条目，再点取消">数据问题 ${stats.issues}</span>`
    : "");
}

function renderTopics() {
  const grid = $("topic-grid");
  if (!topicEntries.length) {
    grid.innerHTML = topicLoading
      ? '<div class="empty-state" style="grid-column:1/-1"><div class="es-icon">⏳</div>'
        + '<div class="es-title">加载中…</div></div>'
      : '<div class="empty-state" style="grid-column:1/-1"><div class="es-icon">🏆</div>'
        + '<div class="es-title">库中暂无条目</div>'
        + '<div class="es-hint">录入历史赛题后，可直接按编号取题面一键生成工程。</div></div>';
    $("topic-stats").textContent = "";
    $("topic-year-chips").innerHTML = "";
    $("topic-browse-msg").textContent = "";
    return;
  }
  const f = topicFilterContext();
  const rows = topicSortEntries(topicFilterEntries(topicEntries, f),
    { by: topicUI.sortBy, dir: topicUI.sortDir });
  grid.innerHTML = rows.length
    ? rows.map((t) => topicCardHTML(t, topicGroupVocab)).join("")
    : '<div class="empty-state" style="grid-column:1/-1"><div class="es-icon">🔍</div>'
      + '<div class="es-title">没有匹配的赛题</div>'
      + '<div class="es-hint">换一个关键词，或点击「清空过滤」恢复全量。</div></div>';
  grid.querySelectorAll("[data-topic-del]").forEach((b) =>
    b.addEventListener("click", () => deleteTopic(b.dataset.topicDel)));
  grid.querySelectorAll("[data-topic-use]").forEach((b) =>
    b.addEventListener("click", () => useTopic(b.dataset.topicUse)));
  grid.querySelectorAll("[data-topic-view]").forEach((b) =>
    b.addEventListener("click", () => viewTopicDetail(b.dataset.topicView)));
  renderTopicYearChips();
  renderTopicStats();
  $("topic-browse-msg").textContent = "";
}

// 页图懒取 memo（工单 topic-library-ui/04）：Map key → {ok, pages} |
// {ok:false, message}。业务 400（数据现状，重试无意义）缓存；网络 /
// 服务端错误（e.status 缺失或 ≥500）不缓存——瞬时故障重开可重试
// （对偶 pdf 轮 loadPdfPages 只缓存 400 的先例）。
const topicPageCache = new Map();

async function loadTopicPageState(key) {
  if (topicPageCache.has(key)) return topicPageCache.get(key);
  try {
    const data = await apiGet(`/api/topics/${encodeURIComponent(key)}/pages`);
    const cached = { ok: true, pages: data.pages || [] };
    topicPageCache.set(key, cached);
    return cached;
  } catch (e) {
    const cached = { ok: false, message: e.message };
    if (e.status && e.status < 500) topicPageCache.set(key, cached);  // 业务 400 缓存
    return cached;
  }
}

function renderTopicPages(box, cached) {
  box.innerHTML = cached.ok
    ? (cached.pages.length ? topicPagesHTML(cached.pages) : '<span class="muted">无页图</span>')
    : topicPagesErrorHTML(cached.message);
}

/** 赛题详情弹窗：元数据 + 题面全文 + 页图懒加载 + 操作（用此题生成 / 编辑 /
 * 删除）。复用 .ref-files-overlay 遮罩与关闭模式（Esc / × / 点遮罩）；
 * 数据 = 浏览列表缓存同源（不另发请求）。编辑按钮的打开行为归工单 05。 */
export async function viewTopicDetail(key) {
  const entry = (topicEntries || []).find((t) => t.key === key);
  if (!entry) { toast("info", "未找到赛题 " + key); return; }
  const overlay = document.createElement("div");
  overlay.className = "ref-files-overlay";
  overlay.innerHTML = `
    <div class="ref-files-modal topic-modal">
      <div class="ref-files-head">
        <strong>赛题详情 · ${esc(key)}</strong>
        <button class="ref-files-close" title="关闭">×</button>
      </div>
      <div class="ref-detail-scroll">${topicDetailHTML(entry, topicGroupVocab)}</div>
    </div>`;
  const close = () => overlay.remove();
  overlay.querySelector(".ref-files-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  overlay.addEventListener("remove", () => document.removeEventListener("keydown", onKey));
  document.body.appendChild(overlay);
  // 操作按钮：用此题生成 / 编辑 / 删除先关弹窗（useTopic 切 tab、deleteTopic 刷新列表）
  overlay.querySelectorAll("[data-topic-use]").forEach((b) =>
    b.addEventListener("click", () => { close(); useTopic(key); }));
  overlay.querySelectorAll("[data-topic-edit]").forEach((b) =>
    b.addEventListener("click", () => { close(); viewTopicEdit(key); }));
  overlay.querySelectorAll("[data-topic-del]").forEach((b) =>
    b.addEventListener("click", () => { close(); deleteTopic(key); }));
  // 题面全文「展开/收起」：折叠态 52vh 可滚，展开态全文直读
  const expandBtn = overlay.querySelector("[data-topic-expand]");
  const problemEl = overlay.querySelector(".topic-detail-problem");
  expandBtn.addEventListener("click", () => {
    const expanded = problemEl.classList.toggle("expanded");
    expandBtn.textContent = expanded ? "收起" : "展开全文";
  });
  // 页图懒取三态：加载中 / 成功（memo 缓存）/ 失败（后端 400 中文原因）
  const pagesBox = overlay.querySelector("[data-topic-pages]");
  pagesBox.innerHTML = '<span class="muted">页图加载中…</span>';
  const cached = await loadTopicPageState(key);
  renderTopicPages(pagesBox, cached);
}

/** 赛题编辑弹窗：全字段表单（题面 / 附带程序 / 功能组）+ 保存 PUT 三态。
 * 复用 .ref-files-overlay 遮罩与关闭模式；年份 + 编号只读展示（身份不可改）；
 * 成功 = 刷新列表（health 服务端重算）+ 关窗，失败 = 弹窗内显示 400 中文
 * 原因（磁盘零变化）。 */
export async function viewTopicEdit(key) {
  const entry = (topicEntries || []).find((t) => t.key === key);
  if (!entry) { toast("info", "未找到赛题 " + key); return; }
  const overlay = document.createElement("div");
  overlay.className = "ref-files-overlay";
  overlay.innerHTML = `
    <div class="ref-files-modal topic-modal">
      <div class="ref-files-head">
        <strong>编辑赛题 · ${esc(key)}</strong>
        <button class="ref-files-close" title="关闭">×</button>
      </div>
      <div class="ref-detail-scroll">${topicEditHTML(entry, topicGroupVocab)}</div>
      <div class="error topic-edit-msg"></div>
    </div>`;
  const close = () => overlay.remove();
  overlay.querySelector(".ref-files-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  overlay.addEventListener("remove", () => document.removeEventListener("keydown", onKey));
  document.body.appendChild(overlay);
  const problemEl = overlay.querySelector(".topic-edit-problem");
  const programsEl = overlay.querySelector(".topic-edit-programs");
  const saveBtn = overlay.querySelector("[data-topic-save]");
  const msgBox = overlay.querySelector(".topic-edit-msg");
  saveBtn.addEventListener("click", async () => {
    const check = topicEditValidate({ problem_text: problemEl.value });
    if (!check.ok) {
      msgBox.textContent = check.message;
      return;
    }
    const payload = topicEditPayload({
      problem_text: problemEl.value,
      programs: programsEl.value,
      hint_module_groups: [...overlay.querySelectorAll("[data-topic-group]:checked")]
        .map((c) => c.dataset.topicGroup),
    });
    saveBtn.disabled = true;
    saveBtn.textContent = "保存中…";
    msgBox.textContent = "";
    try {
      await apiPut(`/api/topics/${encodeURIComponent(key)}`, payload);
      topicPageCache.delete(key);  // 题面变了 → 页图定位缓存失效
      overlay.remove();
      toast("ok", "已保存赛题 " + key);
      loadTopics();  // health（程序悬空）服务端重算，全量刷新
    } catch (e) {
      msgBox.textContent = e.message;
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = "保存";
    }
  });
}

function clearTopicFilter() {
  topicUI.q = ""; topicUI.year = ""; topicUI.health = false;
  $("topic-filter").value = "";
  renderTopics();
}

export function initTopicToolbar() {
  $("topic-filter").addEventListener("input", () => {
    clearTimeout(topicSearchTimer);
    // 防抖回调里直接读 DOM（不依赖事件对象 target 的异步引用——派发后就失效）
    topicSearchTimer = setTimeout(() => { topicUI.q = $("topic-filter").value; renderTopics(); }, 150);
  });
  $("topic-filter").addEventListener("keydown", (e) => { if (e.key === "Escape") clearTopicFilter(); });
  $("topic-sort").addEventListener("change", (e) => { topicUI.sortBy = e.target.value; renderTopics(); });
  $("topic-sort-dir").addEventListener("click", () => {
    topicUI.sortDir = topicUI.sortDir === "asc" ? "desc" : "asc";
    $("topic-sort-dir").textContent = topicUI.sortDir === "asc" ? "↑ 升序" : "↓ 降序";
    renderTopics();
  });
  $("topic-filter-clear").addEventListener("click", clearTopicFilter);
  // chips 事件委托（行内动态渲染）；再点已选中项 = 取消该维度过滤
  $("topic-year-chips").addEventListener("click", (e) => {
    const b = e.target.closest("[data-topic-chip]"); if (!b) return;
    topicUI.year = topicUI.year === b.dataset.topicChip ? "" : b.dataset.topicChip;
    renderTopics();
  });
  // 统计条红段（数据问题）：点击 = 只看问题条目，再点取消（与过滤 / 排序正交）
  $("topic-stats").addEventListener("click", (e) => {
    if (!e.target.closest("[data-topic-health]")) return;
    topicUI.health = !topicUI.health;
    renderTopics();
  });
}
initTopicToolbar();

// 功能组词表（hint 悬空判定数据源）：/api/modules 派生；未配置 / 拉取失败 =
// 空词表（hint 方向降级不判定，不误报）。
export async function loadTopicGroupVocabulary() {
  try {
    topicGroupVocab = topicGroupVocabulary(await apiGet("/api/modules"));
  } catch (e) { topicGroupVocab = {}; }
  if (topicEntries.length) renderTopics();  // 词表到达后重渲染（⚠ 收敛）
}

export async function loadTopics() {
  loadTopicArchiveLink();
  try {
    topicLoading = true;
    renderTopics();  // 加载态（本地 API 快，瞬时闪过）
    topicEntries = await apiGet("/api/topics");
    topicLoading = false;
    renderTopics();
  } catch (e) {
    topicLoading = false;
    $("topic-browse-msg").textContent = e.message;
  }
}

export async function deleteTopic(key) {
  if (!await confirmModal({
    title: "删除赛题条目？",
    message: "删除赛题 " + key + " 的整个条目目录（含题面与原 PDF）？",
    danger: true,
    confirmText: "确认删除",
  })) return;
  try {
    await apiDelete(`/api/topics/${encodeURIComponent(key)}`);
    loadTopics();
  } catch (e) { toast("error", e.message); }
}

export function renderProofreadRows() {
  const box = $("topic-proofread-rows");
  box.innerHTML = "";
  if (!topicRows.length) {
    box.innerHTML = '<div class="muted">校对表为空（条目已全部删除），请重新上传拆条。</div>';
    return;
  }
  topicRows.forEach((t, i) => {
    const div = document.createElement("div");
    div.className = "proofread-row";
    div.innerHTML = `
      <input type="text" placeholder="年份" title="年份（4 位）" value="${esc(t.year)}">
      <input type="text" placeholder="题号" title="题号（如 C）" value="${esc(t.number)}">
      <textarea placeholder="题面全文（可修剪尾部杂项 / 评分汇总）">${esc(t.problem_text)}</textarea>
      <button class="danger" title="删除该条草稿">✕</button>`;
    const inputs = div.querySelectorAll("input, textarea");
    inputs[0].addEventListener("input", (e) => (topicRows[i].year = e.target.value.trim()));
    inputs[1].addEventListener("input", (e) => (topicRows[i].number = e.target.value.trim()));
    inputs[2].addEventListener("input", (e) => (topicRows[i].problem_text = e.target.value));
    div.querySelector("button").addEventListener("click", () => {
      topicRows.splice(i, 1);
      renderProofreadRows();
    });
    box.appendChild(div);
  });
}

$("btn-topic-split").addEventListener("click", async () => {
  $("topic-split-msg").classList.remove("ok");  // 早退路径（无文件）也按错误红显
  $("topic-split-msg").textContent = "";
  $("topic-proofread").classList.add("hidden");
  const file = $("topic-pdf").files[0];
  if (!file) { $("topic-split-msg").textContent = "请先选择 PDF 文件"; return; }
  $("btn-topic-split").disabled = true;
  $("btn-topic-split").innerHTML = '<span class="spinner"></span>拆条中…';
  try {
    const form = new FormData();
    form.append("upload", file);
    const data = await handle(await fetch("/api/topics/split", { method: "POST", body: form }));
    topicPdfFile = file;
    topicRows = data.topics.map((t) => ({ year: t.year, number: t.number, problem_text: t.problem_text }));
    renderProofreadRows();
    $("topic-proofread").classList.remove("hidden");
    $("topic-split-msg").classList.add("ok");
    $("topic-split-msg").textContent = "拆出 " + topicRows.length + " 条赛题草稿，请逐条校对后确认入库。";
  } catch (e) {
    $("topic-split-msg").classList.remove("ok");
    $("topic-split-msg").textContent = e.message;
  } finally {
    $("btn-topic-split").disabled = false;
    $("btn-topic-split").innerHTML = "重新拆条";
  }
});

$("btn-topic-confirm").addEventListener("click", async () => {
  $("topic-confirm-msg").classList.remove("ok");  // 早退路径（空校对表）也按错误红显
  $("topic-confirm-msg").textContent = "";
  if (!topicRows.length) { $("topic-confirm-msg").textContent = "校对表为空，无可入库条目"; return; }
  if (!topicPdfFile) { $("topic-confirm-msg").textContent = "原 PDF 已丢失，请重新上传拆条"; return; }
  $("btn-topic-confirm").disabled = true;
  $("btn-topic-confirm").innerHTML = '<span class="spinner"></span>入库中…';
  try {
    const form = new FormData();
    form.append("pdf", topicPdfFile);
    form.append("payload", JSON.stringify({ entries: topicRows, program_dirs: [] }));
    const data = await handle(await fetch("/api/topics/confirm", { method: "POST", body: form }));
    $("topic-confirm-msg").classList.add("ok");
    $("topic-confirm-msg").textContent = "已入库 " + data.topics.length + " 条："
      + data.topics.map((t) => t.key).join("、");
    topicRows = [];
    topicPdfFile = null;
    $("topic-proofread").classList.add("hidden");
    $("topic-pdf").value = "";
    loadTopics();
  } catch (e) {
    $("topic-confirm-msg").classList.remove("ok");
    $("topic-confirm-msg").textContent = e.message;
  } finally {
    $("btn-topic-confirm").disabled = false;
    $("btn-topic-confirm").innerHTML = "确认入库";
  }
});
