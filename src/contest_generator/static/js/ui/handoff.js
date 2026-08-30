// ui/handoff.js — 第 12 步交接提示词卡的新手说明胶水（工单 newcomer-glossary/03）：
// 「去任务推进」按钮点击 → 滚到第 11 步卡并激活「任务推进」页签——跳转单源
// 在 ui/goto-tasks.js（工单 beginner-gap-closure/02：第 9 步结果区共用同一实现）。
import { $ } from "/js/app.js";
import { goTaskProgress } from "./goto-tasks.js";

export function initHandoffNote() {
  $("btn-goto-tasks")?.addEventListener("click", goTaskProgress);
}
