// fx/md.js — Markdown 资料库纯函数（工单 wiki-materials/02，对偶 fx/pdf.js）。
// Markdown 素材（如立创地猛星移植手册批次）的清单过滤/排序/统计/行渲染：
// 无 PDF 专属语义（页数/重复/回收/健康），渲染预览走 fx/markdown.js 同管线。
// 域内常量无；esc / formatSize 单源取自 fx/core.js。
import { esc, formatSize } from "./core.js";

// mdEncodedPath(relPath)：相对路径逐段编码（每段 encodeURIComponent，
// 不编码段间 "/"——段内特殊字符安全、分隔符保留；预览 URL 用）。
export function mdEncodedPath(relPath) {
  return relPath.split("/").map(encodeURIComponent).join("/");
}

// mdFileUrl(relPath)：素材库 Markdown 全文 URL（段编码 + 库相对路径）。
export function mdFileUrl(relPath) {
  return "/api/materials-md/" + mdEncodedPath(relPath);
}

// mdAssetUrl(relPath)：素材库 Markdown 附属资源（手册图片等）URL（段编码）。
export function mdAssetUrl(relPath) {
  return "/api/materials-md-assets/" + mdEncodedPath(relPath);
}

// mdAssetImageUrl(mdRelPath, src)：预览图片 URL（fx/markdown.js imageUrl 回调）。
// http(s) 外链透传；其余按标准 Markdown 语义「相对 .md 所在目录」归一到素材库
// 相对路径 → 资产端点（wiki 手册约定：md 在批次根、图片在批次根 images/ 下，
// 两义一致；子目录 md 按所在目录归一，引用与本文件同目录的图）。
// 注意与 ui/codeeditor.js 的本地 mdImageUrl（/api/code/raw 预览图）同名异物——
// 端点不同、签名不同（那边是 (src)），命名用 mdAssetImageUrl 区分。
// ../ 越界 / 绝对路径 / 非 http 协议的引用面判定由 fx/markdown.js
// isSafeImageSrc 先行拒绝——本回调只做归一，不复判。
export function mdAssetImageUrl(mdRelPath, src) {
  const s = String(src == null ? "" : src).trim().replace(/^(\.\/)+/, "");
  if (!s) return "";
  if (/^https?:/i.test(s)) return s;
  const rel = String(mdRelPath || "");
  const dir = rel.includes("/") ? rel.slice(0, rel.lastIndexOf("/")) : "";
  return mdAssetUrl(dir ? dir + "/" + s : s);
}

// mdSubdir(relPath)：批次内子目录（rel 去掉批次段与文件名；空 = 批次根）
export function mdSubdir(relPath) {
  const parts = String(relPath || "").split("/");
  return parts.slice(1, -1).join("/");
}

// formatMtime(epochSec)：UNIX 秒 → 本地 "YYYY-MM-DD HH:mm"；缺失/非法 → "—"
// （对偶 pdf formatMtime——独立复刻避免 ui 层跨域 import；实现一致）
export function formatMtime(epochSec) {
  if (epochSec == null) return "—";
  const d = new Date(Number(epochSec) * 1000);
  if (!Number.isFinite(d.getTime())) return "—";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// mdFilterEntries(mds, f)：f={q, batch}。q 大小写不敏感子串匹配文件名 /
// 批次 / 目录 / 完整路径（四合一）；batch 空串 = 该维度不过滤。
export function mdFilterEntries(mds, f) {
  const q = String((f && f.q) || "").trim().toLowerCase();
  const batch = (f && f.batch) || "";
  return (mds || []).filter((m) => {
    if (batch && m.batch !== batch) return false;
    if (q) {
      const hay = [m.name, m.batch, mdSubdir(m.rel_path || ""), m.rel_path];
      if (!hay.some((s) => String(s == null ? "" : s).toLowerCase().includes(q))) return false;
    }
    return true;
  });
}

// mdSortEntries(mds, s)：s={by:'name'|'batch'|'subdir'|'size'|'mtime',
// dir:'asc'|'desc'}；返回新数组（不改原数组）；稳定排序 → 同键保持列表序；
// 数值键（大小 / 修改时间）按数值比较，文本键按 localeCompare。
export function mdSortEntries(mds, s) {
  const by = (s && s.by) || "name";
  const dir = (s && s.dir) === "desc" ? -1 : 1;
  const key = (m) => {
    if (by === "size") return Number(m.size_bytes || 0);
    if (by === "mtime") return Number(m.mtime || 0);
    if (by === "batch") return String(m.batch || "");
    if (by === "subdir") return mdSubdir(m.rel_path || "");
    return String(m.name || "");
  };
  const out = (mds || []).slice();
  out.sort((a, b) => {
    const av = key(a), bv = key(b);
    const cmp = (typeof av === "number" && typeof bv === "number")
      ? (av === bv ? 0 : (av < bv ? -1 : 1))
      : String(av).localeCompare(String(bv));
    return cmp * dir;
  });
  return out;
}

// mdStats(mds)：统计（对传入集合计算——统计条随过滤结果联动）。
// {total, totalBytes, batchCount, batchCounts}；batchCounts 供批次 chips 计数。
export function mdStats(mds) {
  const list = mds || [];
  const batchCounts = {};
  let totalBytes = 0;
  for (const m of list) {
    if (m.batch) batchCounts[m.batch] = (batchCounts[m.batch] || 0) + 1;
    totalBytes += Number(m.size_bytes || 0);
  }
  return { total: list.length, totalBytes,
           batchCount: Object.keys(batchCounts).length, batchCounts };
}

// mdStatsText(stats)：统计条文案（formatSize 注入；0 字节不显示「总体积」段）。
export function mdStatsText(stats) {
  const parts = ["共 " + stats.total + " 篇"];
  if (stats.totalBytes) parts.push("总体积 " + formatSize(stats.totalBytes));
  parts.push(stats.batchCount + " 个批次");
  return parts.join(" · ");
}

// mdChipRowHTML(options, selected)：批次筛选 chips 纯函数（对偶 pdfChipRowHTML，
// 换 data-md-chip 属性）；selected 命中项加 on 类（'' = 未选中）。
export function mdChipRowHTML(options, selected) {
  return (options || []).map((o) =>
    `<button type="button" class="lib-chip${o.value === selected ? " on" : ""}" data-md-chip="${esc(o.value)}">${esc(o.label)}${o.count != null ? "（" + o.count + "）" : ""}</button>`
  ).join("");
}

// mdRowHTML(m, {preview})：行渲染（标题 + 文件名小字 + 完整路径 tooltip、批次 chip、
// 目录列、大小、修改时间、操作按钮）。preview = 是否渲染「预览」钮
// （一律渲染——Markdown 全文由前端拉取页内渲染，无浏览器原生视图）。
// 主行显示 title（服务端取首页标题；空回退文件名），文件名缩为第二行小字。
export function mdRowHTML(m) {
  const subdir = mdSubdir(m.rel_path || "");
  const title = (m.title && String(m.title).trim()) || m.name;
  const fileLine = title !== m.name
    ? `<div class="md-row-file">${esc(m.name)}</div>` : "";
  return `<tr>
    <td class="desc-cell" title="${esc(m.rel_path)}"><a href="#" data-open-md="${esc(m.rel_path)}" title="${esc(m.rel_path)}">${esc(title)}</a>${fileLine}${m.size_bytes > 1024 * 1024 ? '<span class="badge pdf-broken">⚠ 超预览上限</span>' : ""}</td>
    <td><span class="lib-chip">${esc(m.batch)}</span></td>
    <td class="muted" title="${esc(subdir || "批次根")}">${esc(subdir || "—")}</td>
    <td class="muted">${formatSize(m.size_bytes)}</td>
    <td class="muted">${formatMtime(m.mtime)}</td>
    <td><button data-open-md="${esc(m.rel_path)}" title="新标签打开原文（服务端全文端点）">打开</button> <button data-md-preview="${esc(m.rel_path)}" title="页内渲染预览（代码块高亮）">预览</button> <button data-md-copy="${esc(m.rel_path)}" title="复制相对路径">复制路径</button></td>
  </tr>`;
}

// —— 预览弹窗（对偶 showPdfDetail，正文渲染走 fx/markdown.js）——
// mdPreviewBodyHTML(content, m)：已渲染 HTML 的弹窗体——纯函数层不解析
// markdown（渲染管线在 ui 层按需 import fx/markdown.js，保持纯函数无重依赖）；
// 本函数只包壳（标题 + 路径 + 元数据行）。
export function mdPreviewShellHTML(m) {
  const subdir = mdSubdir(m.rel_path || "");
  return `<div class="ref-detail-meta">
    <div class="ref-detail-title">${esc(m.name)}</div>
    <div class="ref-detail-row"><span class="ref-detail-k">路径</span><span class="mono" style="word-break:break-all">${esc(m.rel_path)}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">批次</span><span><span class="lib-chip">${esc(m.batch)}</span></span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">目录</span><span>${esc(subdir || "—")}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">大小</span><span>${formatSize(m.size_bytes)}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">修改时间</span><span>${formatMtime(m.mtime)}</span></div>
  </div>`;
}

if (typeof window !== "undefined") {
  Object.assign(window, { mdEncodedPath, mdSubdir, formatMtime, mdFilterEntries, mdSortEntries, mdStats, mdStatsText, mdChipRowHTML, mdRowHTML, mdPreviewShellHTML, mdFileUrl, mdAssetUrl, mdAssetImageUrl });
}
