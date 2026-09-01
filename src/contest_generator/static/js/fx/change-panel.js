// fx/change-panel.js — 「磁盘变更」面板条目渲染纯函数（工单 code-ide-flow/03）
//
// IDE 底部面板（与编译面板并列）：基线 vs 磁盘的未确认变更集 → 文件级条目
// HTML——状态徽章（新 / 变 / 消失）+ 相对路径 + 修改时间/大小；added/modified
// 条目为跳转按钮（data-change-path 交事件层），removed 置灰不可点；
// main.c 的 modified 条目带行级 diff 区（details 默认折叠，复用
// fx/diff.js mainDiffHTML 单源渲染——同一主题化行级展示）。
// 纯函数：无 DOM / 网络 / localStorage（模块约定见 fx/core.js 头部）。
import { esc, formatSize } from "./core.js";
import { mainDiffHTML } from "./diff.js";
import { isMainCPath } from "./code.js";

// 状态徽章（文案单源——面板与摘要共用同一状态词映射）
const STATUS_BADGE = {
  added: ["b-added", "新"],
  modified: ["b-modified", "变"],
  removed: ["b-removed", "消失"],
};

// fmtMtime(mtimeNs)：纳秒字符串 → 可读时间「MM-DD HH:mm」（无/非法 → ""）。
// 展示用（mtime 事实源仍是字符串比较，不在本函数）。
function fmtMtime(mtimeNs) {
  const ns = Number(mtimeNs);
  if (!Number.isFinite(ns) || ns <= 0) return "";
  const d = new Date(Math.floor(ns / 1e6));
  if (Number.isNaN(d.getTime())) return "";
  const p = (x) => String(x).padStart(2, "0");
  return p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
}

// changeSummaryText(entries)：计数摘要「N 个新增 · M 个修改 · K 个消失」；
// 空 → 「没有磁盘变更」（面板头部状态行文案）。
export function changeSummaryText(entries) {
  const count = (st) => (entries || []).filter((e) => e.status === st).length;
  const a = count("added");
  const m = count("modified");
  const r = count("removed");
  if (!a && !m && !r) return "没有磁盘变更";
  const parts = [];
  if (a) parts.push(a + " 个新增");
  if (m) parts.push(m + " 个修改");
  if (r) parts.push(r + " 个消失");
  return parts.join(" · ");
}

// changeEntryHTML(entry)：单条目 HTML——按钮（added/modified，data-change-
// path + data-change-status 交事件层跳转）/ span（removed 置灰）；main.c
// modified 条目带行级 diff 区（details 折叠；无 mainDiff 数据 → 占位文案）。
function changeEntryHTML(e) {
  const st = STATUS_BADGE[e.status] ? e.status : "modified";
  const badge = STATUS_BADGE[st];
  const meta = (fmtMtime(e.mtime_ns) + (e.size_bytes !== "" && e.size_bytes != null
    ? " · " + formatSize(e.size_bytes) : "")).trim();
  const core = '<span class="code-change-badge ' + badge[0] + '">' + badge[1] + "</span>"
    + '<span class="code-change-path"><code>' + esc(e.path == null ? "" : e.path) + "</code></span>"
    + '<span class="code-change-meta muted">' + esc(meta) + "</span>";
  let out;
  if (st === "removed") {
    out = '<span class="code-change-item disabled" data-change-path="'
      + esc(e.path || "") + '" data-change-status="removed" aria-disabled="true">'
      + core + "</span>";
  } else {
    out = '<button type="button" class="code-change-item" data-change-path="'
      + esc(e.path || "") + '" data-change-status="' + st + '">' + core + "</button>";
  }
  if (st === "modified" && isMainCPath(e.path)) {
    const diffBlock = e.mainDiff
      ? mainDiffHTML(e.mainDiff, "磁盘")
      : '<div class="muted">main.c 行级差异不可用（内容未变化、无旧版本快照或差异过大）。</div>';
    out += '<details class="code-change-diff"><summary>行级改动（main.c）</summary>'
      + '<div class="code-change-diff-body">' + diffBlock + "</div></details>";
  }
  return '<li>' + out + "</li>";
}

// changesPanelHTML(entries)：面板条目列表（ul.code-change-list）；空数组 →
// 空串（空态由调用方放置——面板显示「没有磁盘变更」隐含收起语义）。
export function changesPanelHTML(entries) {
  const items = entries || [];
  if (!items.length) return "";
  return '<ul class="code-change-list">' + items.map(changeEntryHTML).join("") + "</ul>";
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    changesPanelHTML,
    changeSummaryText,
  });
}
