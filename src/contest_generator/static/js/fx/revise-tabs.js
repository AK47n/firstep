// fx/revise-tabs.js — 第11步「修订与深化」卡内页签纯函数（工单 step11-tabs-ui/01：
// 页签条标记 / 徽章文案规则 / 方向键循环 / 面板 id 映射）。无 DOM / fetch——
// node:test 直测（tests/js/revise-tabs.test.mjs）。模块约定见 fx/core.js 头部。
import { esc } from "./core.js";

// 页签定义（key = data-tab / 面板后缀；label = 页签文案）。
// 主路径「任务推进」居首（工单 beginner-gap-closure/01：与教程「任务推进（主路径）」定位一致）。
export const REVISE_TABS = [
  { key: "tasks", label: "任务推进" },
  { key: "revise", label: "修订" },
  { key: "params", label: "参数速调" },
  { key: "delivery", label: "交付" },
];

/** tab key → 面板 id（index.html 中 section.revise-panel 的 id 契约）。 */
export function revisePanelFor(tab) {
  return "revise-panel-" + tab;
}

/** 页签条标记：badges = {key: 文本}；徽章 span 恒渲染（空文本加 hidden），
 * 便于 ui 层就地刷新 textContent 而不重建按钮（保焦点 / aria 状态）。
 * aria-controls / aria-selected / roving tabindex（active=0）一次给全。 */
export function reviseTabsHTML(tabs, active, badges) {
  return (tabs || []).map((t) => {
    const key = t.key;
    const on = key === active;
    const badge = (badges || {})[key] || "";
    let cls = "revise-tab";
    if (on) cls += " active";
    return '<button type="button" class="' + cls + '" role="tab" id="revise-tab-'
      + key + '" data-tab="' + key + '" aria-controls="' + revisePanelFor(key)
      + '" aria-selected="' + (on ? "true" : "false") + '" tabindex="' + (on ? 0 : -1)
      + '"><span class="revise-tab-label">' + esc(t.label) + '</span>'
      + '<span class="revise-tab-badge' + (badge ? "" : " hidden") + '">'
      + esc(badge) + "</span></button>";
  }).join("");
}

/** 徽章文案规则：各分区状态快照 → 徽章文本（空串 = 不显示）。
 * - revise:   {loaded}            已加载上下文 → ✓
 * - tasks:    {done, total}       已拆解 → done/total（total=0 不显示）
 * - params:   {count}             已扫描且 count>0 → N
 * - delivery: {checked, ok}       已检查 → ✓/⚠ */
export function reviseTabBadge(kind, snap) {
  snap = snap || {};
  switch (kind) {
    case "revise": return snap.loaded ? "✓" : "";
    case "tasks": {
      const total = Number(snap.total) || 0;
      return total > 0 ? (Number(snap.done) || 0) + "/" + total : "";
    }
    case "params": return (Number(snap.count) || 0) > 0 ? String(snap.count) : "";
    case "delivery":
      if (!snap.checked) return "";
      return snap.ok ? "✓" : "⚠";
    default: return "";
  }
}

/** 方向键循环：index 移动 dir 步（±1，Home/End 由 ui 层直给 0/count-1），
 * 在 [0, count) 内回绕；count=0 返回 -1。 */
export function reviseTabNext(index, dir, count) {
  const n = Math.max(0, Math.floor(Number(count) || 0));
  if (n === 0) return -1;
  const i = Number.isFinite(Number(index)) ? Math.floor(Number(index)) : 0;
  return ((i + dir) % n + n) % n;
}

// window 桥（fx 模块通用兼容层，见 fx/core.js：44）：供 index.html 直调 /
// 旧脚本内联引用的同名全局；node 测试环境无 window。
if (typeof window !== "undefined") {
  Object.assign(window, { reviseTabsHTML, reviseTabBadge, reviseTabNext, revisePanelFor });
}
