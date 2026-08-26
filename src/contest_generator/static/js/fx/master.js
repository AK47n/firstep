// fx/master.js — 母版库纯函数（工单 frontend-es-modules/05，迁自 index.html
// master 域纯函数组：表格行 / 删除确认 / 详情弹窗 / 关键文件清单行 / 内容
// 端点 URL 拼装）。域内常量无；esc 单源取自 fx/core.js。模块约定见 fx/core.js 头部。
import { esc } from "./core.js";

// masterTableRowHTML(m)：母版库表格行纯函数——平台展示名（platform_label，
// 缺省回退 platform）、提炼来源 join("、")、入库警告 join("；")、详情 + 删除
// 按钮（data-master-detail / data-master-del）。m = /api/masters 条目。
export function masterTableRowHTML(m) {
  return `<tr>
    <td class="slug">${esc(m.platform_label || m.platform)}</td>
    <td class="muted">${esc(m.sources.join("、") || "—")}</td>
    <td class="muted">${esc(m.warnings.join("；") || "—")}</td>
    <td>
      <button data-master-detail="${esc(m.platform)}">详情</button>
      <button class="danger" data-master-del="${esc(m.platform)}">删除</button>
    </td>
  </tr>`;
}

// masterDeleteConfirmHTML(m)：删除确认弹窗内容纯函数——平台展示名 + 元数据
// （平台标识 / 提炼来源 / 关键文件数）+ 不可恢复警告 + 确认/取消双钮。
export function masterDeleteConfirmHTML(m) {
  const files = (m.key_files || []).length;
  return `<div class="ref-detail-meta">
    <div class="ref-detail-title">${esc(m.platform_label || m.platform)}</div>
    <div class="ref-detail-row"><span class="ref-detail-k">平台标识</span><span class="mono">${esc(m.platform)}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">提炼来源</span><span>${esc(m.sources.join("、") || "—")}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">关键文件</span><span>${files} 项预览清单</span></div>
    <div class="ref-detail-note">删除后该平台母版目录与元数据一并移除，<strong>不可恢复</strong>——该平台的生成将找不到母版。确认删除？</div>
  </div>
  <div class="pdf-detail-actions">
    <button type="button" class="danger" data-master-del-confirm>确认删除</button>
    <button type="button" data-master-del-cancel>取消</button>
  </div>`;
}

// masterFileURL(platform, path)：关键文件内容端点 URL 拼装——platform 与
// path 逐段 encodeURIComponent（对偶 ref 轮 href 先例，路径经编码不进 URL 面）。
export function masterFileURL(platform, path) {
  return "/api/masters/" + encodeURIComponent(platform) + "/files/"
    + path.split("/").map(encodeURIComponent).join("/");
}

// masterKeyFileRowHTML(f)：清单行——相对路径 mono + label + 大小 + 缺失 ⚠。
// f = key_files 条目 {path, label, size_bytes, exists}；缺失项禁用不可点。
export function masterKeyFileRowHTML(f) {
  const size = typeof f.size_bytes === "number"
    ? (f.size_bytes >= 1048576
        ? (f.size_bytes / 1048576).toFixed(1) + " MB"
        : f.size_bytes >= 1024
          ? (f.size_bytes / 1024).toFixed(1) + " KB"
          : f.size_bytes + " B")
    : "—";
  return `<li><button type="button" class="master-file-btn"
      data-master-file="${esc(f.path)}"${f.exists ? "" : " disabled"}>
      <span class="master-file-name">${esc(f.path)}</span>
      <span class="muted">${esc(f.label)} · ${size}${f.exists ? "" : " · ⚠ 缺失"}</span>
    </button></li>`;
}

// masterDetailHTML(m)：详情弹窗内容——元数据段（平台 / 来源 / 警告 / 文件数）
// + 文件清单段 + 内容段（点击行按需加载全文）。
export function masterDetailHTML(m) {
  const files = m.key_files || [];
  return `<div class="ref-detail-meta">
    <div class="ref-detail-row"><span class="ref-detail-k">平台标识</span>
      <span class="mono">${esc(m.platform)}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">提炼来源</span>
      <span>${esc((m.sources || []).join("、") || "—")}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">入库警告</span>
      <span>${esc((m.warnings || []).join("；") || "—")}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">关键文件</span>
      <span>${files.length} 项</span></div>
  </div>
  <div class="topic-detail-problem-title">关键文件清单</div>
  <ul class="master-detail-files">${files.length
    ? files.map(masterKeyFileRowHTML).join("")
    : '<li class="muted">未配置关键文件清单</li>'}</ul>
  <div class="topic-detail-problem-title">文件内容</div>
  <div data-master-content><span class="muted">点击上方文件加载全文（纯文本，按需取）。</span></div>`;
}

if (typeof window !== "undefined") {
  Object.assign(window, { masterTableRowHTML, masterDeleteConfirmHTML, masterFileURL, masterKeyFileRowHTML, masterDetailHTML });
}
