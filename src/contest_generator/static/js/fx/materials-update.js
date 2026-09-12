// fx/materials-update.js — 资料库更新纯函数（工单 materials-update/06）
//
// 展示层单源：检查结果区（baseline-missing / 无更新 / 有更新 → 弹窗）、
// 批次选择弹窗（勾选列表 + 全选 + 已选大小）、下载进度（总进度条 + 当前卷 +
// 速度 + 剩余时间）、完成 / 失败结果。后端契约见
// src/contest_generator/materials_update.py 与 materials_task.py。
import { esc } from "./core.js";

/** 检查结果 → 设置页结果区 HTML（弹窗由 ui 层在「查看更新」时打开）。 */
export function materialsCheckCardHTML(check) {
  if (check.error === "baseline-missing") {
    // 无基线 = 无从算增量 → 直接把主按钮切成「一键下载完整 firstep」
    // （工单 full-download/05 的双轨选路：按钮 id 由 ui 层接线到全量流程）
    return `<div class="error">${esc(check.message || "本地资料库版本未知，无法增量更新")}</div>
      <div class="row" style="margin-top:var(--space-2)">
        <button id="btn-materials-full-download" type="button" class="primary breathe" data-ico="download">一键下载完整 firstep</button>
        <span class="muted">本地还没有资料库基线清单（资料库版本未知），无法只下变化的部分；下载完整包后会自动记下基线，以后就只下增量了。</span>
      </div>`;
  }
  if (check.error === "network") {
    return `<div class="error">${esc(check.message || "检查资料库更新失败（网络原因）")}</div>`;
  }
  if (check.error === "no-release" || check.error === "bad-manifest") {
    return `<div class="muted">${esc(check.message || "暂无资料库更新")}</div>`;
  }
  const latest = check.latest_version || "?";
  if (!check.update_available) {
    return `<div class="ok">资料库已是最新版本 v${esc(latest)}</div>`;
  }
  const totalMb = Math.round((check.total_size_bytes || 0) / 1024 / 1024);
  const deleted = check.deleted_batches || [];
  const delNote = deleted.length
    ? `<div class="warning" style="margin-top:var(--space-1)">另有 ${deleted.length} 个整批将被移除（${esc(deleted.map((d) => d.name).join("、"))}）</div>`
    : "";
  return `<div class="update-result">
    <div>发现资料库新版本：<b>v${esc(latest)}</b>（当前 v${esc(check.current_version || "?")}，增量共约 ${totalMb} MB）
      <button id="btn-materials-pick" type="button" class="primary breathe" data-ico="download" style="margin-left:var(--space-2)">选择下载</button>
      <button id="btn-materials-apply-all" type="button" data-ico="download">全部下载</button>
    </div>
    ${delNote}
    <div class="muted" style="margin-top:var(--space-1)">按批次增量下载，只传变化的部分；下载中可后台继续。</div>
  </div>`;
}

/** 批次勾选聚合：选中的 part 汇总 → {totalSize, count, slugs}。 */
export function aggregateSelection(check, selectedSlugs) {
  const sel = new Set(selectedSlugs);
  let total = 0;
  let count = 0;
  const slugs = [];
  for (const b of check.batches || []) {
    if (sel.has(b.slug)) {
      total += b.size_bytes || 0;
      count += b.parts ? b.parts.length : 0;
      slugs.push(b.slug);
    }
  }
  return { totalSize: total, partCount: count, slugs };
}

/** 选择弹窗内容（extra 传入 ui 层的弹窗骨架）：批次勾选列表 + 全选/反选 +
 *  已选大小。opts = {check, selected: Set, onToggle 由 ui 层处理}。 */
export function materialsPickHTML(check, selected) {
  const rows = (check.batches || []).map((b) => {
    const checked = selected.has(b.slug) ? "checked" : "";
    const maybePart = b.parts && b.parts.length > 1 ? `（${b.parts.length} 卷）` : "";
    return `<label class="materials-batch-row" data-slug="${esc(b.slug)}">
      <input type="checkbox" data-batch-check value="${esc(b.slug)}" ${checked}>
      <span class="materials-batch-name">${esc(b.name)}</span>
      <span class="materials-batch-meta">${b.modify_count || 0} 改 ${b.add_count || 0} 增 ${b.del_count || 0} 删 · ${Math.round((b.size_bytes || 0) / 1024 / 1024)} MB${maybePart}</span>
    </label>`;
  }).join("");
  return `<div class="materials-pick-list">${rows}</div>`;
}

/** 弹窗底部：已选大小 + 开始/稍后按钮（返回纯 HTML，按钮 id 交 ui 层）。 */
export function materialsPickFooterHTML(check, selected) {
  const agg = aggregateSelection(check, [...selected]);
  const mb = Math.round(agg.totalSize / 1024 / 1024);
  return `<div class="materials-pick-footer">
    <span class="muted">已选 ${agg.slugs.length} 个批次 · 共 ${mb} MB · ${agg.partCount} 卷</span>
    <button type="button" class="primary breathe" id="btn-materials-start" data-ico="download">开始下载</button>
    <button type="button" data-confirm-cancel>稍后</button>
  </div>`;
}

/** 进度视图（status = /api/update/materials/status 轮询）。 */
export function materialsProgressHTML(status) {
  const total = status.total_bytes || 0;
  const done = status.total_downloaded_bytes || 0;
  const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
  const speed = status.speed_bps || 0;
  const speedText = speed > 0 ? (speed / 1024 / 1024).toFixed(1) + " MB/s" : "—";
  const remainText = speed > 0 && total > done
    ? `剩余 ${Math.max(1, Math.ceil((total - done) / speed))} 秒` : "…";
  const parts = (status.parts || []).map((p) => {
    const pPct = p.total_bytes > 0 ? Math.round((p.downloaded_bytes / p.total_bytes) * 100) : 0;
    const mark = p.ok ? "✓" : "";
    return `<div class="materials-part-row">
      <span class="materials-part-name">${esc(p.name)}${mark}</span>
      <span class="materials-part-meta">${pPct}%</span>
    </div>`;
  }).join("");
  const stateText = materialsStateText(status.state);
  return `<div class="materials-progress">
    <div class="ok">${esc(stateText)}</div>
    <div class="progress"><div class="progress-fill" style="width:${pct}%"></div></div>
    <div class="muted" style="margin:var(--space-1) 0">${done} / ${total} 字节（${pct}%）· 速度 ${speedText} · ${remainText}</div>
    ${parts}
  </div>`;
}

/** 状态文案（无对应 = 空串）。 */
export function materialsStateText(state) {
  return {
    idle: "等待开始…",
    downloading: "正在下载资料库增量包…",
    applying: "下载完成，正在应用到资料库…",
    done: "资料库更新完成",
    failed: "资料库更新失败",
    cancelled: "已取消",
    partial: "部分批次已更新",
  }[state] || "";
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    materialsCheckCardHTML,
    aggregateSelection,
    materialsPickHTML,
    materialsPickFooterHTML,
    materialsProgressHTML,
    materialsStateText,
  });
}
