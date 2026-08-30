// ui/goto-nav.js — 「切页签 + 可选聚焦」跳转原语单源（工单 ux-walkthrough-02/06
// 评审整改）：从 ui/nav-jump.js 拆出——nav-jump 的既有目的就是「避免各处内联
// 重写同一段跳转」，但 settings.js 不能 import nav-jump（其 import settings 会
// 形成回边），故把与 settings 无关的原语落在本模块：nav-jump（重新导出）与
// settings 共用，无环、无重复。
import { $ } from "/js/app.js";

/** 切到指定页签（tab = 顶部导航 data-tab 值）+ 可选聚焦 / 滚动到元素。 */
export function gotoNavTab(tab, focusId) {
  const btn = document.querySelector('nav button[data-tab="' + tab + '"]');
  if (btn) btn.click();
  if (focusId) {
    const el = $(focusId);
    if (el) {
      el.focus();
      el.scrollIntoView({ block: "center" });
    }
  }
}
