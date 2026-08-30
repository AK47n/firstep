// ui/pdf.js — PDF 资料库 tab DOM 胶水（阶段 2 工单 05）
//
// 素材库全量 PDF 浏览 / 客户端即时检索 / 排序 / 统计 / 直开预览 / 详情弹窗 /
// 疑似重复回收删除（对偶参考文件库）。纯件在 fx/pdf.js（过滤/排序/统计/健康/
// 行渲染/详情/回收 URL 等全量），本模块只做 DOM 转发与事件接线。
import { $, apiGet, apiPost, toast, toastError } from "/js/app.js";
import { esc } from "/js/fx/core.js";
import { confirmModal } from "/js/ui/confirm.js";
import {
  pdfHealth, pdfBroken, pdfFilterEntries, pdfSortEntries,
  pdfStats, pdfStatsText, pdfChipRowHTML, pdfRowHTML, pdfPagesUrl, pdfPagesText,
  pdfDetailHTML, pdfTrashUrl, pdfRefsUrl, pdfTrashMessage, pdfDupRemainText, pdfTrashBodyHTML,
  pdfFileUrl,
} from "/js/fx/pdf.js";

// —— 纯函数组在 fx/pdf.js（本模块顶部 import，含域内全部过滤/排序/统计/健康/
// 渲染纯函数）——
// pdfHealthPredicates(pdfs)：健康谓词装配（对偶 ref 系列「行渲染与统计渲染
// 共用同一定义，防两处漂移」契约——renderPdfs 与 renderPdfStats 都从这里
// 取同一组谓词；统计条「共 N 份」随 health 过滤收缩，与表格行数一致）。
function pdfHealthPredicates(pdfs) {
  const h = pdfHealth(pdfs);
  return { isBroken: pdfBroken, isDup: (p) => h.dupPaths.has(p.rel_path) };
}

const pdfPageCache = new Map(); // rel_path → Promise<number | "error">
// loadPdfPages(relPath)：页数懒取 memo——并发重复 = 同一 promise 去重；
// never-reject，失败 resolve("error")。确定态语义：400（损坏/非法/缺失）→
// "error" 落缓存（文件已坏，重试无益）；网络错误 / 500（服务器缺陷）→ 不落
// 缓存，下次打开重试；number = 页数。
function loadPdfPages(relPath) {
  if (!pdfPageCache.has(relPath)) {
    pdfPageCache.set(relPath, apiGet(pdfPagesUrl(relPath))
      .then((d) => Number(d.pages))
      .catch((e) => {
        if (!(e && e.status === 400)) pdfPageCache.delete(relPath);
        return "error"; // 本次仍显示「无法读取」；400 落缓存、其余可重试
      }));
  }
  return pdfPageCache.get(relPath);
}

// copyPdfPath(text)：复制相对路径（clipboard API；失败降级由调用方提示）。
async function copyPdfPath(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch { return false; }
}

// showPdfDetail(pdf)：轻量详情弹窗（对偶 showReferenceDetail：遮罩 + × /
// 遮罩点击 / Esc 关闭；打开 = window.open 原生预览；复制 = 原始 rel_path）。
function showPdfDetail(pdf) {
  const overlay = document.createElement("div");
  overlay.className = "ref-files-overlay";
  // 健康标注（工单 04/06）：全量派生，弹窗内同步行内徽章；dup 组对象供
  // 组级「保留一份删其余」按钮（无组 = 单文件不在重复组，仅单删）。
  const h = pdfHealth(pdfCache);
  const dupGroup = h.dupGroups.find((g) => g.paths.includes(pdf.rel_path));
  const flags = { broken: pdfBroken(pdf), dup: h.dupPaths.has(pdf.rel_path), group: dupGroup };
  overlay.innerHTML = `<div class="ref-files-modal">
    <div class="ref-files-head"><strong>PDF 文件详情</strong><button class="ref-files-close" title="关闭">×</button></div>
    <div class="ref-detail-scroll">${pdfDetailHTML(pdf, null, flags)}</div>
  </div>`;
  const close = () => overlay.remove();
  overlay.querySelector(".ref-files-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  overlay.addEventListener("remove", () => document.removeEventListener("keydown", onKey));
  overlay.querySelectorAll("[data-pdf-open]").forEach((b) =>
    b.addEventListener("click", (e) => {
      e.preventDefault();
      window.open(pdfFileUrl(b.dataset.pdfOpen), "_blank"); // 浏览器原生 PDF 预览
    }));
  overlay.querySelectorAll("[data-pdf-copy]").forEach((b) =>
    b.addEventListener("click", async () => {
      const ok = await copyPdfPath(b.dataset.pdfCopy);
      const msg = overlay.querySelector(".pdf-detail-copy-msg");
      if (msg) msg.textContent = ok ? "已复制相对路径" : "复制失败，请手动复制";
    }));
  // 删除入口（工单 06）：详情数据同源（openPdfTrashConfirm 仍走 pdfCache 查
  // 对象，避免 dataset 里的 stale 数据与页码缓存不一致）；先关详情再开确认
  // ——确认弹窗是独立交互层，不叠层（遮罩点击/Esc 语义干净，用户不会被
  // 两层弹窗困住）。
  overlay.querySelectorAll("[data-pdf-delete],[data-pdf-delete-group]").forEach((b) =>
    b.addEventListener("click", () => {
      const rp = b.dataset.pdfDelete || b.dataset.pdfDeleteGroup;
      const pdf = (pdfCache || []).find((p) => p.rel_path === rp);
      if (!pdf) { toast("info", "未找到该 PDF（列表可能已刷新）"); return; }
      close();
      openPdfTrashConfirm(pdf, b.dataset.pdfDeleteGroup ? dupGroup : null);
    }));
  document.body.appendChild(overlay);
  // 页数懒取落盘（memo 命中则同步返回；槽判空防弹窗已关闭——DOM 分离后
  // querySelector 仍返回节点，写入无害，但保持防御语义）
  loadPdfPages(pdf.rel_path).then((v) => {
    const slot = overlay.querySelector("[data-pdf-pages]");
    if (slot) slot.innerHTML = pdfPagesText(v);
  });
}

// —— 工单 06：疑似重复回收删除（用户裁决 r2）——
// 删除 = 移入回收目录 sources/.trash-pdf/<日期>/<rel_path 镜像>（不真删：
// git 忽略 + 可手动恢复 + git 历史双保险）；仅疑似重复组成员可删
// （f.isDup 命中 / 详情弹窗 dup+group 标注），损坏与健康文件不可删。
// pdfTrashUrl / pdfDupRemainText / pdfTrashBodyHTML 在 fx/pdf.js。
// 工单 ux-walkthrough-02/15：迁移到共享 confirmModal 工厂（与模块/赛题/参考一致）。
// 工单 ux-walkthrough-02/16：任意健康文件可删；确认前取「被参考条目」列表
// 决定影响说明（被引用 → 条目无法打开；否则可恢复）。
async function openPdfTrashConfirm(pdf, group) {
  const mode = group ? "group" : "one";
  const hint = "sources/.trash-pdf/" + pdfTrashDate() + "/" + (pdf.rel_path || "");
  let refTitles = [];
  let refKnown = true;
  if (!group) {   // 组级文案固定（组内疑似重复），无需引用查询（评审整改）
    try {
      const refs = await apiGet(pdfRefsUrl(pdf.rel_path));
      refTitles = Array.isArray(refs.titles) ? refs.titles : [];
    } catch (e) { refKnown = false; }   // 查询失败：中性提示，不断言「未被引用」（spec 轴评审整改）
  }
  const ok = await confirmModal({
    title: mode === "group" ? "保留一份删其余？" : "删除此文件？",
    message: mode === "group"
      ? "组内疑似重复：将删除除保留文件外的其余成员（移入回收目录）。"
      : pdfTrashMessage(refTitles, refKnown),
    extra: pdfTrashBodyHTML(pdf, mode, group, hint),
    confirmText: mode === "group" ? "确认删除其余" : "确认删除",
  });
  if (!ok) return;
  if (group) await confirmTrashGroup(pdf, group, () => {});
  else await confirmTrashPdf(pdf.rel_path, () => {});
}

// pdfTrashDate()：本地日期 YYYY-MM-DD（回收去向提示文案——服务端按同规则
// 落目录，跨时区/午夜差一天仅影响提示文字，不落错处）。
function pdfTrashDate() {
  const t = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${t.getFullYear()}-${pad(t.getMonth() + 1)}-${pad(t.getDate())}`;
}

// confirmTrashPdf(relPath, close)：POST 回收端点 → 关确认弹窗 → toast →
// 缓存失效 + 全量重拉（pdfPageCache 同步清该文件页数——已回收，详情不再命中）。
// 工厂弹窗已由确认路径关闭（close 为兼容参数）；失败 = toastError（可复制重试）。
async function confirmTrashPdf(relPath, close) {
  try {
    await apiPost(pdfTrashUrl(relPath));
    if (close) close(); // 成功后必关（不关会残留弹窗挡住后续交互）
    toast("ok", "已移入回收目录");
    pdfPageCache.delete(relPath);
    loadPdfs();
  } catch (e) { toastError(e); } // 失败：toast 长错误可复制（工单 ux-walkthrough-02/11）
}

// confirmTrashGroup(pdf, group, close)：组级「保留一份删其余」——循环 POST
// 组内除 pdf 之外的全部成员（保留对象不动）；全部成功才关弹窗（部分失败 =
// toast 报错 + 弹窗保留可重试；已成功的成员重试时 400「不存在」由后端语义
// 兜底——同批重试幂等性靠文件消失后的 400 保护，不误删）。
async function confirmTrashGroup(pdf, group, close) {
  const others = (group.paths || []).filter((p) => p !== pdf.rel_path);
  try {
    for (const rp of others) await apiPost(pdfTrashUrl(rp));
    if (close) close();
    toast("ok", `已移入回收目录（${others.length} 份）`);
    others.forEach((rp) => pdfPageCache.delete(rp));
    loadPdfs();
  } catch (e) { toastError(e); }
}

// —— 工具栏状态与渲染（对偶 ref 系列）：过滤条件集中于此，事件层只转发 ——
const pdfUI = { q: "", batch: "", sortBy: "name", sortDir: "asc", health: "" }; // health: "" | "dup" | "broken"
const pdfFilterContext = () => ({ ...pdfUI });
let pdfCache = [];        // 全量（GET /api/pdfs 无参，客户端即时过滤排序统计）
let pdfSearchTimer = null;

function renderPdfChips() {
  // chips 计数 = 全量（维度概览）；统计条 = 过滤结果（随过滤联动）
  const stats = pdfStats(pdfCache);
  const batches = Object.keys(stats.batchCounts).sort((a, b) => a.localeCompare(b));
  $("pdf-batch-chips").innerHTML = pdfChipRowHTML([
    { value: "", label: "全部", count: stats.total },
    ...batches.map((b) => ({ value: b, label: b, count: stats.batchCounts[b] })),
  ], pdfUI.batch);
}

function renderPdfStats() {
  // 与 renderPdfs 共用同一组健康谓词（行渲染/统计渲染同一口径，防漂移）
  const f = pdfFilterContext();
  Object.assign(f, pdfHealthPredicates(pdfCache));
  const filtered = pdfFilterEntries(pdfCache, f);
  // 红段 = 全量口径（对偶参考库 dangling 红段：真值不随过滤收缩——注意
  // 参考库 dangling 计数随过滤收缩，pdf 健康红段有意全量：问题总数恒显），
  // 点击 = 只看该类（再点取消），与关键字 / 批次 chips 正交
  const h = pdfHealth(pdfCache);
  const parts = [esc(pdfStatsText(pdfStats(filtered)))];
  if (h.dupGroups.length) {
    parts.push(`<span class="lib-stats-red${pdfUI.health === "dup" ? " on" : ""}" data-pdf-health="dup" title="同名同大小疑似重复（全量口径）">疑似重复 ${h.dupGroups.length} 组</span>`);
  }
  if (h.broken.size) {
    parts.push(`<span class="lib-stats-red${pdfUI.health === "broken" ? " on" : ""}" data-pdf-health="broken" title="0 字节损坏文件（全量口径）">损坏 ${h.broken.size} 份</span>`);
  }
  // 可点击筛选的可见提示（ux-polish-02/08）：不再靠 title 猜
  if (h.dupGroups.length || h.broken.size) {
    parts.push('<span class="lib-stats-hint">（点击可筛选）</span>');
  }
  $("pdf-stats").innerHTML = parts.join(" · ");
}

function renderPdfs() {
  const f = pdfFilterContext();
  // 行内徽章 = 全量口径恒显；pdfFilterEntries 仅在 health 置位时消费谓词
  Object.assign(f, pdfHealthPredicates(pdfCache));
  const rows = pdfSortEntries(pdfFilterEntries(pdfCache, f),
    { by: pdfUI.sortBy, dir: pdfUI.sortDir });
  if (!pdfCache.length) {
    $("pdf-rows").innerHTML = '<tr><td colspan="6" class="empty-td"><div class="empty-state"><div class="es-icon">📄</div><div class="es-title">素材库中暂无 PDF</div><div class="es-hint">把赛题配套 PDF 放进资料库目录后点「刷新」，这里会按批次列出。</div></div></td></tr>';
  } else if (!rows.length) {
    // 过滤后的空结果 ≠ 库为空：提示「清空过滤」而不是「暂无 PDF」
    $("pdf-rows").innerHTML = '<tr><td colspan="6" class="empty-td"><div class="empty-state"><div class="es-icon">🔍</div><div class="es-title">没有匹配的 PDF 文件</div><div class="es-hint">换一个关键词，或点击「清空过滤」恢复全量。</div></div></td></tr>';
  } else {
    $("pdf-rows").innerHTML = rows.map((p) => pdfRowHTML(p, f)).join("");
  }
  $("pdf-rows").querySelectorAll("[data-open-pdf]").forEach((el) =>
    el.addEventListener("click", (e) => {
      e.preventDefault();
      window.open(pdfFileUrl(el.dataset.openPdf), "_blank"); // 浏览器原生 PDF 预览
    }));
  // 详情按钮接线（工单 03）：弹窗打开 = 行数据透传（数据同源，零重复请求）
  $("pdf-rows").querySelectorAll("[data-pdf-detail]").forEach((b) =>
    b.addEventListener("click", () => {
      const pdf = (pdfCache || []).find((p) => p.rel_path === b.dataset.pdfDetail);
      if (pdf) showPdfDetail(pdf);
      else toast("info", "未找到该 PDF（列表可能已刷新）");
    }));
  // 行内删除接线（工单 06）：仅疑似重复行渲染按钮（pdfRowHTML 判定），
  // 确认弹窗打开 = 行数据透传（与详情同源）
  $("pdf-rows").querySelectorAll("[data-pdf-trash]").forEach((b) =>
    b.addEventListener("click", () => {
      const pdf = (pdfCache || []).find((p) => p.rel_path === b.dataset.pdfTrash);
      if (pdf) openPdfTrashConfirm(pdf);
      else toast("info", "未找到该 PDF（列表可能已刷新）");
    }));
  renderPdfChips();
  renderPdfStats();
}

function clearPdfFilter() {
  pdfUI.q = ""; pdfUI.batch = ""; pdfUI.health = "";
  $("pdf-filter").value = "";
  renderPdfs();
}

export async function loadPdfs() {
  try {
    // 加载态占位（对偶模块库 / 参考库「正在读取…」）
    $("pdf-rows").innerHTML = '<tr><td colspan="6" class="empty-td"><div class="empty-state"><div class="es-icon">⏳</div><div class="es-title">正在读取 PDF 资料库…</div></div></td></tr>';
    pdfCache = await apiGet("/api/pdfs");
    renderPdfs();
    $("pdf-msg").textContent = "";
  } catch (e) { $("pdf-msg").textContent = e.message; }
}

export function initPdfToolbar() {
  $("pdf-filter").addEventListener("input", (e) => {
    clearTimeout(pdfSearchTimer);
    pdfSearchTimer = setTimeout(() => { pdfUI.q = e.target.value; renderPdfs(); }, 150);
  });
  $("pdf-filter").addEventListener("keydown", (e) => { if (e.key === "Escape") clearPdfFilter(); });
  $("pdf-sort").addEventListener("change", (e) => {
    pdfUI.sortBy = e.target.value;
    if (e.target.value === "mtime") {   // 最近更新默认降序（最新在前，ux-polish-02/08）
      pdfUI.sortDir = "desc";
      $("pdf-sort-dir").textContent = "↓ 降序";
    }
    renderPdfs();
  });
  $("pdf-sort-dir").addEventListener("click", () => {
    pdfUI.sortDir = pdfUI.sortDir === "asc" ? "desc" : "asc";
    $("pdf-sort-dir").textContent = pdfUI.sortDir === "asc" ? "↑ 升序" : "↓ 降序";
    renderPdfs();
  });
  $("pdf-filter-clear").addEventListener("click", clearPdfFilter);
  // 刷新（工单 ux-polish-02/08）：新 PDF 放进素材库目录后一键重拉，保留过滤/排序
  $("pdf-refresh").addEventListener("click", async () => {
    try {
      await loadPdfs();
      toast("ok", "已刷新 PDF 列表");
    } catch (e) { /* loadPdfs 内部已展示错误 */ }
  });
  // 批次 chips 事件委托（行内动态渲染）；再点已选中项 = 取消该维度过滤
  $("pdf-batch-chips").addEventListener("click", (e) => {
    const b = e.target.closest("[data-pdf-chip]"); if (!b) return;
    pdfUI.batch = pdfUI.batch === b.dataset.pdfChip ? "" : b.dataset.pdfChip;
    renderPdfs();
  });
  // 统计条红段（工单 04）：点击 = 只看该类，再点取消（与 q / batch 正交）
  $("pdf-stats").addEventListener("click", (e) => {
    const s = e.target.closest("[data-pdf-health]"); if (!s) return;
    pdfUI.health = pdfUI.health === s.dataset.pdfHealth ? "" : s.dataset.pdfHealth;
    renderPdfs();
  });
}
