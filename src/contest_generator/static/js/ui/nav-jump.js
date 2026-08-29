// ui/nav-jump.js — 「切页签 + 可选聚焦」跳转单源（工单 beginner-guide/02）：
// 由 ui/welcome.js 的原 gotoSettings 泛化——功能入口（欢迎卡 / gen-banner /
// 新手指引教程跳转按钮 / 后续任何「去 XX」按钮）复用同一条路径：触发顶部
// nav 按钮点击 = 复用 tab 切换全部既有逻辑，再可选聚焦目标元素，避免各处
// 内联重写同一段跳转。
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
