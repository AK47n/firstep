// fx/recommend.js — 推荐结果区纯函数（工单 buy-guide/02：库外建议选型参考
// chip 升级）。库外建议（OutOfLibrarySuggestion）的展示层：solutions 词表
// 方案列表 + selected AI 建议高亮。模块约定见 fx/core.js 头部。
// 载荷形状（selection.to_dict 契约）：suggestion =
//   { name, examples[], degraded, solutions[{name, interface, price, note,
//     suitable, recommended, lib_modules[]}], selected }
import { esc } from "./core.js";

// suggestionSolutionBadges(sol, selected)：单方案徽标。recommended = 词表
// 推荐 →「推荐」；lib_modules 非空 = 库内已有对应模块 →「库内已有：…」
// （工单 wordlist-lib-modules/02：不用重复采购，可先看库内模块）；
// selected === sol.name = LLM 按题面建议 →「AI 建议」；可共存；都无 → ""。
// selected 空串（词表外/未选）不高亮。旧载荷无 lib_modules 键 → 无徽章。
export function suggestionSolutionBadges(sol, selected) {
  let out = "";
  if (sol.recommended) {
    out += ' <span class="badge sugg-rec" title="词表推荐方案（价廉/易得/接线简单）">推荐</span>';
  }
  if (Array.isArray(sol.lib_modules) && sol.lib_modules.length) {
    out += ' <span class="badge sugg-lib" title="库内已有对应模块（买件无需重复采购，可先看库内模块）">库内已有：'
      + esc(sol.lib_modules.join(" · ")) + "</span>";
  }
  if (selected && sol.name === selected) {
    out += ' <span class="badge sugg-ai" title="AI 按赛题建议的方案">AI 建议</span>';
  }
  return out;
}

// suggestionOptionRowHTML(sol, selected, decision)：选型参考面板单行——名称 +
// [接口] + [价格] + 徽标（头部行）+ 备注 + 适用（可空字段不渲染）+「就用这个」
// 按钮（data-buy-pick，ui 层委托确定；decision 命中本行时行内显示已定徽标）。
export function suggestionOptionRowHTML(sol, selected, decision) {
  const meta = [];
  if (sol.interface) meta.push(`<span class="sugg-meta">${esc(sol.interface)}</span>`);
  if (sol.price) meta.push(`<span class="sugg-meta">${esc(sol.price)}</span>`);
  // 已定徽标渲染在行首（名称后、接口/价格前——评审项 spec/⑤「已定优先」）
  const decided = decision && decision.source === "wordlist" && decision.name === sol.name
    ? " " + decisionBadgeHTML(decision) : "";
  return `<div class="sugg-row">
    <div class="sugg-head"><span class="sugg-name">${esc(sol.name)}</span>${decided}${meta.join("")}${suggestionSolutionBadges(sol, selected)}<button type="button" class="sugg-pick" data-buy-pick="${esc(sol.name)}">就用这个</button></div>
    ${sol.note ? `<div class="sugg-note">${esc(sol.note)}</div>` : ""}
    ${sol.suitable ? `<div class="sugg-suitable">适用：${esc(sol.suitable)}</div>` : ""}
  </div>`;
}

// suggestionOptionsHTML(s, st)：选型参考面板（solutions 空 → ""，不渲染面板）。
// 面板 = 方案行（st.decision 供行内已定徽标）+ 「和 AI 商量」讨论区
// （工单 buy-discuss/04/05）。面板展开态由 ui 层渲染时控制（.sugg-wrap active
// 类在 suggestionChipHTML 内按 st.openPanel 输出——渲染函数保持纯函数）。
export function suggestionOptionsHTML(s, st) {
  const sols = s.solutions || [];
  if (!sols.length) return "";
  const state = st || {};
  const rows = sols
    .map((sol) => suggestionOptionRowHTML(sol, s.selected, state.decision))
    .join("");
  return `<div class="sugg-panel"><div class="sugg-panel-title">选型参考（按需采购，价格仅供参考）</div>${rows}${discussionAreaHTML(s, state)}</div>`;
}

// suggestionChipHTML(s, st)：库外建议 chip 完整结构。
// solutions 非空 → .sugg-wrap 包裹（chip + 「⤵ N 方案」计数 + 可展开面板，
// st.openPanel 决定面板展开态——ui 层 state 驱动重渲染，非 DOM classList 直改）；
// solutions 空/旧载荷 → 旧行为（仅 span.chip.out + 需自备）。chip 徽标：已定
// （st.decision）+ AI 建议（s.selected）可共存。
export function suggestionChipHTML(s, st) {
  const note = s.degraded ? "（型号不在词表，按类别展示）" : "";
  const body = esc(s.name)
    + '<span class="reason">需自备' + note
    + (s.examples.length ? "：" + esc(s.examples.join(" / ")) : "") + "</span>";
  const sols = s.solutions || [];
  const state = st || {};
  if (!sols.length) {
    return `<span class="chip out" title="${esc(note)}">${body}</span>`;
  }
  return `<div class="sugg-wrap${state.openPanel ? " active" : ""}" data-sugg-key="${esc(suggestionKey(s))}">
    <span class="chip out sugg-chip" title="点击展开/收起选型参考">${body}<span class="sugg-count">⤵ ${sols.length} 方案</span>${state.decision ? decisionBadgeHTML(state.decision) : ""}</span>
    ${suggestionOptionsHTML(s, state)}
  </div>`;
}

// ===== 已定方案与商量（工单 buy-discuss/04）=====

// localStorage 键（buy-decisions 记忆：重推 / 刷新 / 换题面不丢）
export const BUY_DECISIONS_KEY = "firstep.buy-decisions.v1";

// decisionBadgeHTML(decision)：已定徽标。wordlist = 「✓ 已定：方案名」；
// custom = 「✓ 已定·自定：标题」（用户想法 = 猜想，AI 校核后仍可确定，
// UI 注明「自定」）；无 decision / 缺 name = ""。
export function decisionBadgeHTML(decision) {
  if (!decision || !decision.name) return "";
  const custom = decision.source === "custom";
  const label = custom ? "已定·自定" : "已定";
  return ' <span class="badge sugg-decided" title="'
    + (custom ? "你与 AI 商量后确定的自定方案（AI 审核意见见讨论区）"
      : "你与 AI 商量后确定的词表方案") + '">✓ ' + label + "：" + esc(decision.name) + "</span>";
}

// reviewBadgeHTML(review)：AI 审核三态徽标（feasible 绿 / risky 黄 /
// infeasible 红，复用 badge 语义色）+ reason 文本；无 review = ""。
export function reviewBadgeHTML(review) {
  if (!review || !review.verdict) return "";
  const label = {
    feasible: "AI 审核：可行",
    risky: "AI 审核：有风险",
    infeasible: "AI 审核：不可行",
  }[review.verdict] || "AI 审核";
  return '<span class="badge sugg-review sugg-review-' + esc(review.verdict)
    + '" title="' + esc(review.reason || "") + '">' + label
    + (review.reason ? "：" + esc(review.reason) : "") + "</span>";
}

// decisionPayload(decision)：上行载荷形状（source / name / note / verdict，
// 与 selection.parse_decision 契约对偶——服务端按其校验）；无 = ""。
export function decisionPayload(decision) {
  return decision && decision.name
    ? {
      source: decision.source === "custom" ? "custom" : "wordlist",
      name: String(decision.name),
      note: String(decision.note || ""),
      verdict: String(decision.verdict || ""),
    } : null;
}

// suggestionKey(s)：已定结论的匹配键（建议名——词表外降级后 name 即类别名，
// 重推后同一条建议名不变即可恢复记忆）——与 localStorage 条目键对偶。
export function suggestionKey(s) {
  return String((s && s.name) || "");
}

// loadBuyDecisions(storage)：读已定结论记忆（draft-memory 先例：storage 注入
// 纯函数化）。结果 = {键: decision dict}；损坏 JSON / 无键 = 空对象（不炸）。
export function loadBuyDecisions(storage) {
  let raw = null;
  try { raw = storage.getItem(BUY_DECISIONS_KEY); } catch (e) { return {}; }
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch (e) { return {}; }
}

// saveBuyDecisions(storage, decisions)：写回记忆；失败（隐私模式等）= false
// 静默降级（记忆是增强，不阻断主流程）。
export function saveBuyDecisions(storage, decisions) {
  try {
    storage.setItem(BUY_DECISIONS_KEY, JSON.stringify(decisions || {}));
    return true;
  } catch (e) { return false; }
}

// matchBuyDecision(decisions, key)：按建议名匹配已定结论（无 = null）。
export function matchBuyDecision(decisions, key) {
  const d = decisions && decisions[key];
  return d && typeof d === "object" && !Array.isArray(d) ? d : null;
}

// discussionAreaHTML(s, st)：讨论区纯渲染（工单 buy-discuss/04/05）。
// st = {open: 展开态, busy: 请求中, history: [{role, content}],
//       review: 最近一轮校核意见, decision: 已定结论}；无 solutions
// （无可商量的词表方案）= ""。交互（发送 / 确定按钮）在 ui 层绑定，
// 本函数只出骨架；轮数上限 8（用户消息数 ≥8 = exhausted，输入禁用）。
export function discussionAreaHTML(s, st) {
  const sols = s.solutions || [];
  if (!sols.length) return "";
  const state = st || {};
  const history = Array.isArray(state.history) ? state.history : [];
  const userRounds = history.filter((m) => m.role === "user").length;
  const exhausted = userRounds >= 8;
  const msgs = history.map((m, index) => {
    const ai = m.role === "assistant";
    return '<div class="sugg-msg ' + (ai ? "ai" : "user") + '"><span class="sugg-msg-role">'
      + (ai ? "AI" : "你") + "：</span>" + esc(m.content)
      // AI 审核徽标只贴最近一条 AI 消息（评审项 buy-discuss/03：逐条贴会把
      // 同一校核意见重复贴到历史每条上）
      + (ai && state.review && index === history.length - 1 ? reviewBadgeHTML(state.review) : "") + "</div>";
  }).join("");
  const disabled = state.busy || exhausted ? "disabled" : "";
  return `<div class="sugg-discuss">
    <button type="button" class="sugg-discuss-toggle">和 AI 商量</button>
    <div class="sugg-discuss-box${state.open ? " open" : ""}">
      <div class="sugg-discuss-msgs">${msgs || '<div class="sugg-msg muted">与 AI 讨论选型：说你的情况 / 想法，AI 结合题面与方案校核可行性。</div>'}</div>
      <div class="sugg-discuss-row">
        <input type="text" class="sugg-discuss-input" placeholder="问 AI / 说你的想法（如：我有旧 HC-SR04，想用它）" ${disabled}>
        <button type="button" class="sugg-discuss-send" ${disabled}>发送</button>
        <button type="button" class="sugg-discuss-custom" data-buy-self="1" ${disabled}>就用我提的</button>
      </div>
      <div class="sugg-discuss-note muted">${exhausted ? "已达 8 轮上限：请确定方案（或在输入框写你的想法后点「就用我提的」）。" : "最多 8 轮；你的自定想法会由 AI 校核可行性（顾问非裁判，最终你拍板）。"}</div>
    </div>
  </div>`;
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    suggestionSolutionBadges, suggestionOptionRowHTML,
    suggestionOptionsHTML, suggestionChipHTML,
    BUY_DECISIONS_KEY, decisionBadgeHTML, reviewBadgeHTML, decisionPayload,
    suggestionKey, loadBuyDecisions, saveBuyDecisions, matchBuyDecision,
    discussionAreaHTML,
  });
}
