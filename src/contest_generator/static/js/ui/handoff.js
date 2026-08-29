// ui/handoff.js — 第 12 步交接提示词卡的新手说明胶水（工单 newcomer-glossary/03）：
// 「去任务推进」按钮点击 → 滚动到第 11 步卡并激活「任务推进」页签（复用
// ui/revise-tabs.js 的 switchReviseTab，不新写页签逻辑）；Y4 只做文案 + 跳转。
import { $ } from "/js/app.js";
import { switchReviseTab } from "/js/ui/revise-tabs.js";

/** 去任务推进：滚动到第 11 步卡 + 激活「任务推进」页签（用户主动 → user:true）。 */
export function goTaskProgress() {
  const card = $("card-revise");
  if (card) card.scrollIntoView({ block: "start", behavior: "smooth" });
  switchReviseTab("tasks", { user: true });
}

export function initHandoffNote() {
  $("btn-goto-tasks")?.addEventListener("click", goTaskProgress);
}
