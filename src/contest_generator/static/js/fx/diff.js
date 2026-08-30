// fx/diff.js — 效果 diff 渲染纯函数（工单 diff-restyle/01）：main.c 前后
// 确定性 diff（main_diff）的主题化行级展示——统计行 + 每个 hunk 一个可折叠
// 改动点（标题优先取被替换的 TODO 注释，展开 = 行级着色 diff：新增绿 /
// 删除红 / 上下文灰）。事实源 = 后端真实 diff（不依赖 LLM 自述）。
// 模块约定见 fx/core.js 头部。
import { esc } from "./core.js";

/** 统计行（新增 / 删除 / 处数）；色类 diff-count add|del 走主题变量。
 * name = 实体名（深化 / 任务），文案不写死（任务面板不出现「深化」）。 */
export function diffStatsLineHTML(stats, name) {
  const s = stats || {};
  return '<div class="diff-stats reason"><strong>' + esc(name)
    + "效果：</strong>新增 <span class=\"diff-count add\">+"
    + (s.additions || 0) + "</span> 行 · 删除 <span class=\"diff-count del\">−"
    + (s.deletions || 0) + "</span> 行 · " + (s.hunks || 0) + " 处改动</div>";
}

/** 单行 diff（内容已由后端剥离 +/- 前缀，此处只补符号列与着色）。 */
function diffLineHTML(entry) {
  const kind = entry.kind === "add" ? "add" : entry.kind === "del" ? "del" : "ctx";
  const gutter = kind === "add" ? "+" : kind === "del" ? "−" : " ";
  return '<div class="diff-line diff-' + kind + '"><span class="diff-gutter">'
    + gutter + '</span><span class="diff-text">' + esc(entry.text) + "</span></div>";
}

/** hunk 列表（标题回退「第 N 行附近」；默认折叠，行为与旧版一致）。 */
function diffHunksHTML(hunks) {
  return (hunks || []).map((h) => {
    const title = h.title || "第 " + (h.line || "?") + " 行附近";
    return '<details class="diff-hunk"><summary>' + esc(title)
      + '</summary><div class="diff-body">'
      + (h.lines || []).map(diffLineHTML).join("") + "</div></details>";
  }).join("");
}

/** 深化/任务效果主渲染（main_diff → HTML 块）：统计行 + hunks。
 * main_diff = undefined → 不渲染（旧后端）；null / 空 hunks → 占位提示。 */
export function mainDiffHTML(diff, entity) {
  const name = entity || "深化";
  if (diff === undefined) return "";
  const hunks = (diff && diff.hunks) || [];
  if (!hunks.length) return '<div class="muted" style="margin-top: var(--space-2)">'
    + esc(name) + "未改动 main.c（无差异）。</div>";
  return diffStatsLineHTML(diff.stats, name) + diffHunksHTML(hunks);
}

if (typeof window !== "undefined") {
  Object.assign(window, { mainDiffHTML, diffStatsLineHTML });
}
