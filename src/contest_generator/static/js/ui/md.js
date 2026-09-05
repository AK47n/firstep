// ui/md.js — Markdown 资料库 tab DOM 胶水（工单 wiki-materials/02）
//
// 素材库全量 .md 浏览 / 客户端即时检索 / 排序 / 统计 / 原文打开 / 页内渲染
// 预览（对偶 ui/pdf.js，但无页数/重复/回收——PDF 专属语义不移植）。纯件在
// fx/md.js（过滤/排序/统计/行渲染/弹窗壳），渲染管线 = fx/markdown.js
// parseMarkdownBlocks + markdownPreviewHTML（与 code-viewer md 预览同管线，
// 代码块语言分发/高亮单源）。
import { $, apiGet, toast, toastError, copyText } from "/js/app.js";
import { esc } from "/js/fx/core.js";
import { parseMarkdownBlocks, markdownPreviewHTML } from "/js/fx/markdown.js";
import {
  mdFilterEntries, mdSortEntries, mdStats, mdStatsText, mdChipRowHTML,
  mdRowHTML, mdFileUrl, mdAssetImageUrl, mdPreviewShellHTML,
} from "/js/fx/md.js";

// —— 工具栏状态与渲染（对偶 pdf 系列）——
const mdUI = { q: "", batch: "", sortBy: "mtime", sortDir: "desc" }; // 默认最近更新降序
let mdCache = [];        // 全量（GET /api/materials-md 无参，客户端即时过滤排序统计）
let mdSearchTimer = null;

function renderMdChips() {
  const stats = mdStats(mdCache);
  const batches = Object.keys(stats.batchCounts).sort((a, b) => a.localeCompare(b));
  $("md-batch-chips").innerHTML = mdChipRowHTML([
    { value: "", label: "全部", count: stats.total },
    ...batches.map((b) => ({ value: b, label: b, count: stats.batchCounts[b] })),
  ], mdUI.batch);
}

function renderMdStats() {
  const filtered = mdFilterEntries(mdCache, { q: mdUI.q, batch: mdUI.batch });
  $("md-stats").innerHTML = esc(mdStatsText(mdStats(filtered)));
}

function renderMds() {
  const rows = mdSortEntries(
    mdFilterEntries(mdCache, { q: mdUI.q, batch: mdUI.batch }),
    { by: mdUI.sortBy, dir: mdUI.sortDir });
  if (!mdCache.length) {
    $("md-rows").innerHTML = '<tr><td colspan="6" class="empty-td"><div class="empty-state"><div class="es-icon">📘</div><div class="es-title">素材库中暂无 Markdown</div><div class="es-hint">把 Markdown 手册 / 笔记放进资料库目录后点「刷新」，这里会按批次列出（含立创地猛星移植手册 70 篇）。</div></div></td></tr>';
  } else if (!rows.length) {
    $("md-rows").innerHTML = '<tr><td colspan="6" class="empty-td"><div class="empty-state"><div class="es-icon">🔍</div><div class="es-title">没有匹配的 Markdown 文件</div><div class="es-hint">换一个关键词，或点击「清空过滤」恢复全量。</div></div></td></tr>';
  } else {
    $("md-rows").innerHTML = rows.map((m) => mdRowHTML(m)).join("");
  }
  // 打开原文 = 新标签（服务端 text 全文端点；超限 400 由打开时呈现）
  $("md-rows").querySelectorAll("[data-open-md]").forEach((el) =>
    el.addEventListener("click", (e) => {
      e.preventDefault();
      window.open(mdFileUrl(el.dataset.openMd), "_blank");
    }));
  // 预览 = 页内渲染弹窗（数据同源透传，零重复请求）
  $("md-rows").querySelectorAll("[data-md-preview]").forEach((b) =>
    b.addEventListener("click", () => {
      const m = (mdCache || []).find((x) => x.rel_path === b.dataset.mdPreview);
      if (m) openMdPreview(m);
      else toast("info", "未找到该文件（列表可能已刷新）");
    }));
  // 复制相对路径（对偶 pdf 复制机制）
  $("md-rows").querySelectorAll("[data-md-copy]").forEach((b) =>
    b.addEventListener("click", async () => {
      const m = (mdCache || []).find((x) => x.rel_path === b.dataset.mdCopy);
      if (!m) { toast("info", "未找到该文件（列表可能已刷新）"); return; }
      const ok = await copyText(m.rel_path);
      toast(ok ? "ok" : "error", ok ? "已复制相对路径" : "复制失败，请手动复制");
    }));
  renderMdChips();
  renderMdStats();
}

// —— 预览弹窗：markdown 渲染复用 code-viewer 管线——正文由服务端全文端点
// 拉取（懒取 memo，400 缓存可重试 / 网络 500 不缓存），渲染 = 弹窗壳 +
// 正文滚动区。opts.imageUrl 走 fx/md.js mdAssetImageUrl：相对图片（手册内嵌图，
// 如图片 images/<slug>/imgN.ext）按 .md 所在目录归一到素材库资产端点；http(s) 外链透传。 ——
const mdPreviewCache = new Map(); // rel_path → Promise<{content} | "error">
// 大小上限与后端一致（1MB）——超限文件不拉正文，行内已标 ⚠；预览仍可开
// （弹窗显示元数据 + 明确提示超限，不渲染正文）。
const MD_PREVIEW_MAX_BYTES = 1024 * 1024;

function loadMdText(relPath) {
  if (!mdPreviewCache.has(relPath)) {
    mdPreviewCache.set(relPath, apiGet(mdFileUrl(relPath))
      .catch((e) => {
        if (!(e && e.status === 400)) mdPreviewCache.delete(relPath);
        return "error";
      }));
  }
  return mdPreviewCache.get(relPath);
}

function renderMdBlocks(content, m) {
  const blocks = parseMarkdownBlocks(content || "");
  return markdownPreviewHTML(blocks, {
    imageUrl: (src) => mdAssetImageUrl((m && m.rel_path) || "", src),
  });
}

function openMdPreview(m) {
  const overlay = document.createElement("div");
  overlay.className = "ref-files-overlay";
  overlay.innerHTML = `<div class="ref-files-modal md-preview-modal">
    <div class="ref-files-head"><strong>Markdown 预览</strong><button class="ref-files-close" title="关闭">×</button></div>
    <div class="ref-detail-scroll">${mdPreviewShellHTML(m)}
      <div class="md-preview-body" data-md-body>
        <div class="md-preview-status muted">正读取正文…</div>
      </div>
    </div>
  </div>`;
  const close = () => overlay.remove();
  overlay.querySelector(".ref-files-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  overlay.addEventListener("remove", () => document.removeEventListener("keydown", onKey));
  document.body.appendChild(overlay);
  // 超限文件：Show 元数据 + 提示，不拉正文
  if (Number(m.size_bytes || 0) > MD_PREVIEW_MAX_BYTES) {
    const body = overlay.querySelector("[data-md-body]");
    if (body) body.innerHTML = '<div class="md-preview-status danger">文件超过预览上限（1MB），请用「打开」查看原文。</div>';
    return;
  }
  loadMdText(m.rel_path).then((d) => {
    const body = overlay.querySelector("[data-md-body]");
    if (!body) return; // 弹窗已关
    if (d === "error") {
      body.innerHTML = '<div class="md-preview-status danger">无法读取该文件（缺失/非法/超限），可点「打开」重试原文。</div>';
      return;
    }
    body.innerHTML = renderMdBlocks(d.content, m);
  });
}

function clearMdFilter() {
  mdUI.q = ""; mdUI.batch = "";
  $("md-filter").value = "";
  renderMds();
}

export async function loadMds() {
  try {
    $("md-rows").innerHTML = '<tr><td colspan="6" class="empty-td"><div class="empty-state"><div class="es-icon">⏳</div><div class="es-title">正在读取 Markdown 资料库…</div></div></td></tr>';
    mdCache = await apiGet("/api/materials-md");
    renderMds();
    $("md-msg").textContent = "";
  } catch (e) {
    $("md-rows").innerHTML = '<tr><td colspan="6" class="empty-td"><div class="empty-state">'
      + '<div class="es-icon">⚠️</div><div class="es-title">Markdown 资料库读取失败</div>'
      + '<div class="es-hint">' + esc(e.message) + '；可在设置页检查库目录，或点「刷新」重试。</div>'
      + '</div></td></tr>';
    $("md-msg").textContent = "";
    if ($("md-stats")) $("md-stats").innerHTML = "";
    if ($("md-batch-chips")) $("md-batch-chips").innerHTML = "";
  }
}

export function initMdToolbar() {
  $("md-filter").addEventListener("input", (e) => {
    clearTimeout(mdSearchTimer);
    mdSearchTimer = setTimeout(() => { mdUI.q = e.target.value; renderMds(); }, 150);
  });
  $("md-filter").addEventListener("keydown", (e) => { if (e.key === "Escape") clearMdFilter(); });
  $("md-sort").addEventListener("change", (e) => {
    mdUI.sortBy = e.target.value;
    if (e.target.value === "mtime") {
      mdUI.sortDir = "desc";
      $("md-sort-dir").textContent = "↓ 降序（默认）";
    }
    renderMds();
  });
  $("md-sort-dir").addEventListener("click", () => {
    mdUI.sortDir = mdUI.sortDir === "asc" ? "desc" : "asc";
    $("md-sort-dir").textContent = mdUI.sortDir === "asc" ? "↑ 升序"
      : (mdUI.sortBy === "mtime" ? "↓ 降序（默认）" : "↓ 降序");
    renderMds();
  });
  $("md-filter-clear").addEventListener("click", clearMdFilter);
  $("md-refresh").addEventListener("click", async () => {
    try {
      await loadMds();
      toast("ok", "已刷新 Markdown 列表");
    } catch (e) { /* loadMds 内部已展示错误 */ }
  });
  $("md-batch-chips").addEventListener("click", (e) => {
    const b = e.target.closest("[data-md-chip]"); if (!b) return;
    mdUI.batch = mdUI.batch === b.dataset.mdChip ? "" : b.dataset.mdChip;
    renderMds();
  });
}
