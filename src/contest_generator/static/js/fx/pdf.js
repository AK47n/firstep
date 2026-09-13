// fx/pdf.js — PDF 资料库纯函数（工单 frontend-es-modules/02，迁自 index.html
// pdf 域纯函数组）。域内常量无；esc / formatSize 单源取自 fx/core.js。
// 模块约定见 fx/core.js 头部。
import { esc, formatSize } from "./core.js";

// pdfEncodedPath(relPath)：相对路径逐段编码（每段 encodeURIComponent，
// 不编码段间 "/"——段内特殊字符安全、分隔符保留；预览 / 页数 URL 共用）。
export function pdfEncodedPath(relPath) {
  return relPath.split("/").map(encodeURIComponent).join("/");
}

// pdfFileUrl(relPath)：素材库文件直开 URL（段编码 + 库相对路径）。
// 工单 09 单源修正：05 迁移时主体函数被删而 fx/pdf.js 未补导出，题库
// archive 链接调用点悬空；本函数下沉为纯函数，ui/pdf.js / ui/topic.js 共用。
export function pdfFileUrl(relPath) {
  return "/api/pdfs/" + pdfEncodedPath(relPath);
}

// pdfSubdir(relPath)：批次内子目录（rel 去掉批次段与文件名；空 = 批次根）
export function pdfSubdir(relPath) {
  const parts = String(relPath || "").split("/");
  return parts.slice(1, -1).join("/");
}

// formatMtime(epochSec)：UNIX 秒 → 本地 "YYYY-MM-DD HH:mm"；缺失/非法 → "—"
export function formatMtime(epochSec) {
  if (epochSec == null) return "—";
  const d = new Date(Number(epochSec) * 1000);
  if (!Number.isFinite(d.getTime())) return "—";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// pdfBroken(p)：损坏判据（0 字节 = 无法打开/无内容的空文件）。
// 显式接受字符串 "0"（防御宽松——后端 st_size 为 int，但 Number 防护同理）；
// null/undefined/"" 不判损坏（字段缺失 ≠ 空文件）。
export function pdfBroken(p) {
  return !!(p && (p.size_bytes === 0 || p.size_bytes === "0"));
}

// pdfBadgeTags(broken, dup)：健康徽章 HTML（行内与详情弹窗共用）。
export function pdfBadgeTags(broken, dup) {
  return (broken ? '<span class="badge pdf-broken">⚠ 损坏</span>' : "") +
         (dup ? '<span class="badge pdf-dup">⚠ 疑似重复</span>' : "");
}

// pdfDupGroups(pdfs)：疑似重复分组——同名（大小写不敏感）+ 同大小 +
// 大小 > 0，组内 ≥ 2 成员（0 字节归损坏不参与重复；同名不同大小 = 版本
// 差异不判；判据纯客户端，不读内容 hash）。返回
// [{name, size, count, paths: string[]}]，按组内首成员输入序稳定。
//
// 「不读内容 hash」是**量过之后的决定**（2026-09-13 库去重盘点）：对真实库
// （97 个 PDF / 208 MB）全量 SHA256 只要 1.4s，但算出的重复组 100% 已被本判据
// 覆盖（组内大小全部一致，多抓 0 组）——升级成内容哈希只有维护成本、没有收益。
// 已知边界：内容相同但**换了名字**的重复本判据标不出（那类靠离线盘点清理，
// 见 .scratch/library-dedup-audit/report.md）。改判据前先读
// tests/js/pdf-dup-guard.test.mjs：那条守卫会把形态变化与健全性回归都挡下来。
export function pdfDupGroups(pdfs) {
  const groups = new Map(); // nameLower|size → {name, size, paths}
  for (const p of pdfs || []) {
    if (!p || !(p.size_bytes > 0) || !p.name) continue;
    const key = p.name.toLowerCase() + "|" + p.size_bytes;
    if (!groups.has(key)) groups.set(key, { name: p.name, size: p.size_bytes, paths: [] });
    groups.get(key).paths.push(p.rel_path);
  }
  return [...groups.values()]
    .filter((g) => g.paths.length >= 2)
    .map((g) => ({ ...g, count: g.paths.length }));
}

// pdfHealth(pdfs)：全量健康派生（对偶 refDanglingAnchors——统计条红段与
// 行内徽章用全量口径，不随过滤结果收缩）。返回
// {dupGroups, dupPaths: Set<rel_path>, broken: Set<rel_path>}。
export function pdfHealth(pdfs) {
  const dupGroups = pdfDupGroups(pdfs);
  const dupPaths = new Set();
  for (const g of dupGroups) for (const p of g.paths) dupPaths.add(p);
  const broken = new Set();
  for (const p of pdfs || []) if (pdfBroken(p)) broken.add(p.rel_path);
  return { dupGroups, dupPaths, broken };
}

// pdfFilterEntries(pdfs, f)：f={q, batch, health?, isDup?, isBroken?}。q 大小写
// 不敏感子串匹配文件名 / 批次 / 目录 / 完整路径（四合一）；batch 空串 = 该维度
// 不过滤；health（"" | "dup" | "broken"）与 q / batch 正交——谓词由调用方注入
// （工单 04 用 pdfDupGroups / pdfBroken 组装；health 置位但无谓词 = 该维度
// 不参与，不静默清空）。
export function pdfFilterEntries(pdfs, f) {
  const q = String((f && f.q) || "").trim().toLowerCase();
  const batch = (f && f.batch) || "";
  const health = (f && f.health) || "";
  return (pdfs || []).filter((p) => {
    if (batch && p.batch !== batch) return false;
    if (health === "broken" && (f.isBroken ? !f.isBroken(p) : false)) return false;
    if (health === "dup" && (f.isDup ? !f.isDup(p) : false)) return false;
    if (q) {
      const hay = [p.name, p.batch, pdfSubdir(p.rel_path || ""), p.rel_path];
      if (!hay.some((s) => String(s == null ? "" : s).toLowerCase().includes(q))) return false;
    }
    return true;
  });
}

// pdfSortEntries(pdfs, s)：s={by:'name'|'batch'|'subdir'|'size'|'mtime',
// dir:'asc'|'desc'}；返回新数组（不改原数组）；稳定排序 → 同键保持列表序；
// 数值键（大小 / 修改时间）按数值比较，文本键按 localeCompare。
export function pdfSortEntries(pdfs, s) {
  const by = (s && s.by) || "name";
  const dir = (s && s.dir) === "desc" ? -1 : 1;
  const key = (p) => {
    if (by === "size") return Number(p.size_bytes || 0);
    if (by === "mtime") return Number(p.mtime || 0);
    if (by === "batch") return String(p.batch || "");
    if (by === "subdir") return pdfSubdir(p.rel_path || "");
    return String(p.name || "");
  };
  const out = (pdfs || []).slice();
  out.sort((a, b) => {
    const av = key(a), bv = key(b);
    const cmp = (typeof av === "number" && typeof bv === "number")
      ? (av === bv ? 0 : (av < bv ? -1 : 1))
      : String(av).localeCompare(String(bv));
    return cmp * dir;
  });
  return out;
}

// pdfStats(pdfs)：统计（对传入集合计算——统计条随过滤结果联动）。
// {total, totalBytes, batchCount, batchCounts}；batchCounts 供批次 chips 计数
// （维度概览 = 全量口径；统计条 = 过滤结果口径，调用处分开传）。
export function pdfStats(pdfs) {
  const list = pdfs || [];
  const batchCounts = {};
  let totalBytes = 0;
  for (const p of list) {
    if (p.batch) batchCounts[p.batch] = (batchCounts[p.batch] || 0) + 1;
    totalBytes += Number(p.size_bytes || 0);
  }
  return { total: list.length, totalBytes,
           batchCount: Object.keys(batchCounts).length, batchCounts };
}

// pdfStatsText(stats)：统计条文案（formatSize 注入；0 字节不显示「总体积」段）。
export function pdfStatsText(stats) {
  const parts = ["共 " + stats.total + " 份"];
  if (stats.totalBytes) parts.push("总体积 " + formatSize(stats.totalBytes));
  parts.push(stats.batchCount + " 个批次");
  return parts.join(" · ");
}

// pdfChipRowHTML(options, selected)：批次筛选 chips 纯函数（对偶 refChipRowHTML，
// 换 data-pdf-chip 属性）；selected 命中项加 on 类（'' = 未选中）。
export function pdfChipRowHTML(options, selected) {
  return (options || []).map((o) =>
    `<button type="button" class="lib-chip${o.value === selected ? " on" : ""}" data-pdf-chip="${esc(o.value)}">${esc(o.label)}${o.count != null ? "（" + o.count + "）" : ""}</button>`
  ).join("");
}

// pdfRowHTML(p, f)：行渲染（文件名链接 + 完整路径 tooltip、批次 chip、目录列、
// 大小、修改时间、操作按钮）。f.isBroken / f.isDup 谓词（工单 04 注入）=
// 行内 ⚠ 健康徽章；无谓词不标注。工单 ux-walkthrough-02/16：非损坏文件
// 均可删除（回收），不再只限疑似重复。
export function pdfRowHTML(p, f) {
  const subdir = pdfSubdir(p.rel_path || "");
  const broken = !!(f && f.isBroken && f.isBroken(p));
  const dup = !!(f && f.isDup && f.isDup(p));
  const tags = pdfBadgeTags(broken, dup);
  return `<tr>
    <td class="desc-cell" title="${esc(p.rel_path)}"><a href="#" data-open-pdf="${esc(p.rel_path)}" title="${esc(p.rel_path)}">${esc(p.name)}</a>${tags}</td>
    <td><span class="lib-chip">${esc(p.batch)}</span></td>
    <td class="muted" title="${esc(subdir || "批次根")}">${esc(subdir || "—")}</td>
    <td class="muted">${formatSize(p.size_bytes)}</td>
    <td class="muted">${formatMtime(p.mtime)}</td>
    <td><button data-open-pdf="${esc(p.rel_path)}" title="新标签打开 PDF">打开</button> <button data-pdf-detail="${esc(p.rel_path)}" title="查看完整信息">详情</button>${broken ? "" : ` <button class="danger" data-pdf-trash="${esc(p.rel_path)}" title="移入回收目录（可恢复）">删除</button>`}</td>
  </tr>`;
}

// —— 工单 03：详情弹窗（页数按需懒取 + 复制相对路径）——
// pdfPagesUrl(relPath)：页数端点 URL（复用 pdfEncodedPath 逐段编码，尾缀 /pages）。
export function pdfPagesUrl(relPath) {
  return "/api/pdfs/" + pdfEncodedPath(relPath) + "/pages";
}

// pdfPagesText(pages)：页数三态（null = 读取中 / number = N 页 / "error" = 无法读取）。
export function pdfPagesText(pages) {
  if (pages == null) return '<span class="muted">页数读取中…</span>';
  if (pages === "error") return '<span class="danger">无法读取（文件损坏或为空）</span>';
  return esc(pages) + " 页";
}

// pdfDetailHTML(pdf, pages, flags)：详情弹窗内容（元数据段 + 操作段）。
// 页数懒取三态占位（data-pdf-pages 槽由 showPdfDetail 落盘）；
// flags={broken, dup, group}（工单 04/06）= 标题旁 ⚠ 健康徽章 + 操作段删除
// 按钮（非损坏均可单删（工单 ux-walkthrough-02/16）；dup 额外有组级「保留
// 一份删其余」），缺省不标注不渲染。
export function pdfDetailHTML(pdf, pages, flags = {}) {
  const subdir = pdfSubdir(pdf.rel_path || "");
  const tags = pdfBadgeTags(flags.broken, flags.dup);
  return `<div class="ref-detail-meta">
    <div class="ref-detail-title">${esc(pdf.name)}${tags}</div>
    <div class="ref-detail-row"><span class="ref-detail-k">路径</span><span class="mono" style="word-break:break-all">${esc(pdf.rel_path)}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">批次</span><span><span class="lib-chip">${esc(pdf.batch)}</span></span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">目录</span><span>${esc(subdir || "—")}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">大小</span><span>${formatSize(pdf.size_bytes)}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">修改时间</span><span>${formatMtime(pdf.mtime)}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">页数</span><span data-pdf-pages>${pdfPagesText(pages)}</span></div>
  </div>
  <div class="pdf-detail-actions">
    <button type="button" class="primary" data-pdf-open="${esc(pdf.rel_path)}">打开 PDF</button>
    <button type="button" data-pdf-copy="${esc(pdf.rel_path)}">复制相对路径</button>
    ${flags.broken ? "" : `<button type="button" class="danger" data-pdf-delete="${esc(pdf.rel_path)}">删除此文件</button>`}
    ${flags.group ? `<button type="button" data-pdf-delete-group="${esc(pdf.rel_path)}" title="${esc(pdfDupRemainText(flags.group))}">${esc(pdfDupRemainText(flags.group))}</button>` : ""}
    <span class="pdf-detail-copy-msg muted"></span>
  </div>`;
}

// —— 工单 06：疑似重复回收删除（用户裁决 r2）——
// pdfTrashUrl(relPath)：回收端点 URL（对偶 pdfPagesUrl：逐段编码 + /trash）。
export function pdfTrashUrl(relPath) {
  return "/api/pdfs/" + pdfEncodedPath(relPath) + "/trash";
}

// pdfRefsUrl(relPath)：被参考条目查询 URL（工单 ux-walkthrough-02/16）——
// 删除确认框据此决定影响说明（被参考 → 条目将无法打开；否则可恢复）。
export function pdfRefsUrl(relPath) {
  return "/api/pdfs/" + pdfEncodedPath(relPath) + "/refs";
}

/** 删除确认消息（工单 ux-walkthrough-02/16）：titles = 引用该文件的参考
 * 条目标题列表。被参考 → 点明可能影响（若条目依赖此文件将无法打开——
 * 同名不同内容属保守命中，不写死断言）；未引用 → 明示可恢复；known=false =
 * 引用查询失败（中性提示，spec/standards 轴评审整改）。 */
export function pdfTrashMessage(titles, known) {
  const list = Array.isArray(titles) ? titles.filter(Boolean) : [];
  if (list.length) {
    return "该文件被参考条目「" + list.join("、") + "」引用：若条目依赖此文件，删除后相关文件将无法打开。"
      + "确认移入回收目录？（可从 sources/.trash-pdf/ 手动恢复）";
  }
  if (known === false) {
    return "未能确认该文件是否被参考条目引用：如删除后发现条目文件失效，可从回收目录手动恢复。确认删除？";
  }
  return "该文件未被参考条目引用：删除 = 移入回收目录（不真删，可手动恢复）。确认删除？";
}

// pdfDupRemainText(group)：「保留一份删其余」文案（组级按钮 + 确认标题共用）。
export function pdfDupRemainText(group) {
  const n = Math.max(0, ((group && group.count) || 1) - 1);
  return "保留此文件，删除其余 " + n + " 份";
}

// pdfTrashBodyHTML(pdf, mode, group, trashHint)：回收确认弹窗元数据体（不含
// 按钮——按钮由共享 confirmModal 工厂渲染；工单 ux-walkthrough-02/15 迁移）；
// pdfTrashConfirmHTML = 体 + 双钮（旧手搓弹窗用，测试对偶保留）。
export function pdfTrashBodyHTML(pdf, mode, group, trashHint) {
  const members = (mode === "group" && group && group.paths) ? group.paths : [];
  return `<div class="ref-detail-meta">
    <div class="ref-detail-title">${esc(pdf.name)}${pdfBadgeTags(false, true)}</div>
    <div class="ref-detail-row"><span class="ref-detail-k">完整路径</span><span class="mono" style="word-break:break-all">${esc(pdf.rel_path)}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">大小</span><span>${formatSize(pdf.size_bytes)}</span></div>
    ${members.length ? `<div class="ref-detail-row"><span class="ref-detail-k">组内成员</span><ul class="pdf-trash-members">${members.map((rp) => `<li class="mono">${esc(rp)}</li>`).join("")}</ul></div>` : ""}
    <div class="ref-detail-row"><span class="ref-detail-k">回收去向</span><span class="mono">${esc(trashHint)}</span></div>
    <div class="ref-detail-note">删除 = 移入回收目录（不真删）：文件出现在 <code>sources/.trash-pdf/‹日期›/</code>，git 已忽略、可手动恢复；若该文件被参考库条目引用，删除后条目文件将无法打开。</div>
  </div>`;
}

export function pdfTrashConfirmHTML(pdf, mode, group, trashHint) {
  return pdfTrashBodyHTML(pdf, mode, group, trashHint) + `<div class="pdf-detail-actions">
    <button type="button" class="danger" data-pdf-trash-confirm="${esc(pdf.rel_path)}">确认${mode === "group" ? "删除其余" : "删除"}</button>
    <button type="button" data-pdf-trash-cancel>取消</button>
  </div>`;
}

if (typeof window !== "undefined") {
  Object.assign(window, { pdfEncodedPath, pdfSubdir, formatMtime, pdfBroken, pdfBadgeTags, pdfDupGroups, pdfHealth, pdfFilterEntries, pdfSortEntries, pdfStats, pdfStatsText, pdfChipRowHTML, pdfRowHTML, pdfPagesUrl, pdfPagesText, pdfDetailHTML, pdfTrashUrl, pdfRefsUrl, pdfTrashMessage, pdfDupRemainText, pdfTrashConfirmHTML, pdfTrashBodyHTML });
}
