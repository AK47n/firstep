// fx/settings.js — 设置页折叠纯函数（工单 frontend-es-modules/10，迁自
// index.html 设置域纯函数组：折叠状态解析 / 默认集判定 / 生效值计算 /
// 总开关与计费小节文案 / 折叠态应用）。域内常量 SETTINGS_COLLAPSE_KEY 与
// SETTINGS_DEFAULT_COLLAPSED 随迁并 export（胶水层 saveSettingsCollapse /
// initSettingsCollapse 经 import 取用，单源防漂移）。共享件依赖：
// syncCollapseBtn 由 fx/generate.js 提供（工单 08 已迁，不重复搬）。
// 模块约定见 fx/core.js 头部。
import { syncCollapseBtn } from "./generate.js";

export const SETTINGS_COLLAPSE_KEY = "firstep.settingsCollapse.v1";
export const SETTINGS_DEFAULT_COLLAPSED =
  new Set(["libs", "toolchain", "local-llm", "vision", "ai-billing"]);
export function parseSettingsCollapse(raw) {
  if (!raw) return {};
  try {
    const v = JSON.parse(raw);
    return v && typeof v === "object" && !Array.isArray(v) ? v : {};
  } catch { return {}; }
}
export function settingsDefaultCollapsed(id) {
  return SETTINGS_DEFAULT_COLLAPSED.has(id);
}
export function effectiveCollapsed(id, stored) {
  return id in stored ? !!stored[id] : settingsDefaultCollapsed(id);
}
// 总开关标签：全部折叠 → 「全部展开」，否则「全部收起」
export function settingsMasterLabel(allCollapsed) {
  return allCollapsed ? "全部展开" : "全部收起";
}
// 计费小节折叠按钮读屏文案（区别于卡片的 collapseBtnLabel）
export function sectionCollapseLabel(collapsed) {
  return collapsed ? "展开计费区" : "折叠计费区";
}
// 计费小节头按钮：仅当元素自身是 .settings-collapse 才查后代——不用无条件
// querySelector，否则「卡片内含计费小节」的祖先卡片会被误判为小节
//（（工单 settings-infoarch/02）CDP 回归）
export function settingsSectionHead(elm) {
  return elm.classList.contains("settings-collapse")
    ? elm.querySelector(".settings-collapse-head")
    : null;
}
// 应用折叠态到一个元素：卡片走 .card-collapse（syncCollapseBtn 同步
// title/aria-label），计费小节走 .settings-collapse-head（sectionCollapseLabel）
export function applySettingsCollapseState(elm, collapsed) {
  elm.classList.toggle("collapsed", collapsed);
  const head = settingsSectionHead(elm);
  if (head) {
    head.title = collapsed ? "展开" : "折叠";
    head.setAttribute("aria-label", sectionCollapseLabel(collapsed));
    return;
  }
  const btn = elm.querySelector(".card-collapse");
  if (btn) syncCollapseBtn(btn, collapsed);
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    SETTINGS_COLLAPSE_KEY, SETTINGS_DEFAULT_COLLAPSED,
    parseSettingsCollapse, settingsDefaultCollapsed, effectiveCollapsed,
    settingsMasterLabel, sectionCollapseLabel, settingsSectionHead,
    applySettingsCollapseState,
  });
}
