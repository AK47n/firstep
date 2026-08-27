// fx/recommend.js — 推荐结果区纯函数（工单 buy-guide/02：库外建议选型参考
// chip 升级）。库外建议（OutOfLibrarySuggestion）的展示层：solutions 词表
// 方案列表 + selected AI 建议高亮。模块约定见 fx/core.js 头部。
// 载荷形状（selection.to_dict 契约）：suggestion =
//   { name, examples[], degraded, solutions[{name, interface, price, note,
//     suitable, recommended}], selected }
import { esc } from "./core.js";

// suggestionSolutionBadges(sol, selected)：单方案徽标。recommended = 词表
// 推荐 →「推荐」；selected === sol.name = LLM 按题面建议 →「AI 建议」；
// 可共存；都无 → ""。selected 空串（词表外/未选）不高亮。
export function suggestionSolutionBadges(sol, selected) {
  let out = "";
  if (sol.recommended) {
    out += ' <span class="badge sugg-rec" title="词表推荐方案（价廉/易得/接线简单）">推荐</span>';
  }
  if (selected && sol.name === selected) {
    out += ' <span class="badge sugg-ai" title="AI 按赛题建议的方案">AI 建议</span>';
  }
  return out;
}

// suggestionOptionRowHTML(sol, selected)：选型参考面板单行——名称 + [接口] +
// [价格] + 徽标（头部行）+ 备注 + 适用（可空字段不渲染）。
export function suggestionOptionRowHTML(sol, selected) {
  const meta = [];
  if (sol.interface) meta.push(`<span class="sugg-meta">${esc(sol.interface)}</span>`);
  if (sol.price) meta.push(`<span class="sugg-meta">${esc(sol.price)}</span>`);
  return `<div class="sugg-row">
    <div class="sugg-head"><span class="sugg-name">${esc(sol.name)}</span>${meta.join("")}${suggestionSolutionBadges(sol, selected)}</div>
    ${sol.note ? `<div class="sugg-note">${esc(sol.note)}</div>` : ""}
    ${sol.suitable ? `<div class="sugg-suitable">适用：${esc(sol.suitable)}</div>` : ""}
  </div>`;
}

// suggestionOptionsHTML(s)：选型参考面板（solutions 空 → ""，不渲染面板）。
// 面板默认收起（.sugg-panel display:none），展开由 ui 层给外层
// .sugg-wrap 加 active 类（CSS class toggle，不重渲染）。
export function suggestionOptionsHTML(s) {
  const sols = s.solutions || [];
  if (!sols.length) return "";
  const rows = sols
    .map((sol) => suggestionOptionRowHTML(sol, s.selected))
    .join("");
  return `<div class="sugg-panel"><div class="sugg-panel-title">选型参考（按需采购，价格仅供参考）</div>${rows}</div>`;
}

// suggestionChipHTML(s)：库外建议 chip 完整结构。
// solutions 非空 → .sugg-wrap 包裹（chip + 「⤵ N 方案」计数 + 可展开面板）；
// solutions 空/旧载荷 → 旧行为（仅 span.chip.out + 需自备）。点击展开由
// ui 层委托 .sugg-chip（toggle .sugg-wrap.active），本函数保持纯渲染。
export function suggestionChipHTML(s) {
  const note = s.degraded ? "（型号不在词表，按类别展示）" : "";
  const body = esc(s.name)
    + '<span class="reason">需自备' + note
    + (s.examples.length ? "：" + esc(s.examples.join(" / ")) : "") + "</span>";
  const sols = s.solutions || [];
  if (!sols.length) {
    return `<span class="chip out" title="${esc(note)}">${body}</span>`;
  }
  return `<div class="sugg-wrap">
    <span class="chip out sugg-chip" title="点击展开/收起选型参考">${body}<span class="sugg-count">⤵ ${sols.length} 方案</span></span>
    ${suggestionOptionsHTML(s)}
  </div>`;
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    suggestionSolutionBadges, suggestionOptionRowHTML,
    suggestionOptionsHTML, suggestionChipHTML,
  });
}
