// ui/goto-nav.js — 「切页签 + 可选聚焦」跳转原语单源（工单 ux-walkthrough-02/06
// 评审整改）：从 ui/nav-jump.js 拆出——nav-jump 的既有目的就是「避免各处内联
// 重写同一段跳转」，但 settings.js 不能 import nav-jump（其 import settings 会
// 形成回边），故把与 settings 无关的原语落在本模块：nav-jump（重新导出）与
// settings 共用，无环、无重复。
import { $ } from "/js/app.js";

/** 跳转目标高亮（工单 guide-jump-flash/01）：非交互元素（卡片等）focus()
 * 无可见焦点样式，用户不知道跳到了哪——临时加 .jump-flash 高亮类（CSS
 * 动画描边 + 脉冲微光，见 index.html），定时移除；连续跳转同目标时重置。 */
let _flashTimer = 0;
export function flashJumpTarget(el) {
  el.classList.remove("jump-flash");
  void el.offsetWidth; // 强制 reflow，重启动画
  el.classList.add("jump-flash");
  clearTimeout(_flashTimer);
  _flashTimer = setTimeout(() => el.classList.remove("jump-flash"), 1800);
}

/** 切到指定页签（tab = 顶部导航 data-tab 值）+ 可选聚焦 / 滚动到元素。 */
export function gotoNavTab(tab, focusId) {
  const btn = document.querySelector('nav button[data-tab="' + tab + '"]');
  if (btn) btn.click();
  if (focusId) {
    const el = $(focusId);
    if (el) {
      el.focus();
      el.scrollIntoView({ block: "center" });
      flashJumpTarget(el);
    }
  }
}
