// ui/nav-jump.js — 「切页签 + 可选聚焦」跳转单源（工单 beginner-guide/02）：
// 由 ui/welcome.js 的原 gotoSettings 泛化——功能入口（欢迎卡 / gen-banner /
// 新手指引教程跳转按钮 / 后续任何「去 XX」按钮）复用同一条路径：触发顶部
// nav 按钮点击 = 复用 tab 切换全部既有逻辑，再可选聚焦目标元素，避免各处
// 内联重写同一段跳转。
// 设置页定位（工单 ux-polish-02/03）：gotoSettingsKey 补充「先展开 AI API 卡」
// ——key 输入框藏在可折叠的「AI API」卡内，只聚焦不展开会落空；展开原语
// 来自 ui/settings.js（无回边：settings 不 import 本模块）。
import { $ } from "/js/app.js";
import { expandSettingsCollapse } from "/js/ui/settings.js";

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

/** 去设置页填 key：先展开「AI API」卡（用户手动折叠过也能展开），再切页签 +
 * 聚焦 key 输入框。三个入口共用（欢迎卡 / 生成页横幅 / 设置页横幅）。 */
export function gotoSettingsKey() {
  expandSettingsCollapse("llm-api");
  gotoNavTab("settings", "set-api-key");
}
