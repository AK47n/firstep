// ui/goto-tasks.js — 「去任务推进」跳转单源（工单 beginner-gap-closure/02）：
// 第 9 步生成结果区按钮与第 12 步交接卡按钮共用——滚动到第 11 步卡 +
// 激活「任务推进」页签（复用 ui/revise-tabs.js 的 switchReviseTab，不新写页签逻辑）。
import { $ } from "/js/app.js";
import { switchReviseTab } from "/js/ui/revise-tabs.js";

/** 去任务推进：滚动到第 11 步卡 + 激活「任务推进」页签（用户主动 → user:true）。 */
export function goTaskProgress() {
  const card = $("card-revise");
  if (card) card.scrollIntoView({ block: "start", behavior: "smooth" });
  switchReviseTab("tasks", { user: true });
}
