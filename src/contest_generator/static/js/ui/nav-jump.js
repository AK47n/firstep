// ui/nav-jump.js — 「去设置」跳转组合（工单 beginner-guide/02）：由
// ui/welcome.js 的 gotoSettings 泛化——功能入口（欢迎卡 / gen-banner /
// 新手指引教程跳转按钮 / 后续任何「去 XX」按钮）复用同一条路径：触发顶部
// nav 按钮点击 = 复用 tab 切换全部既有逻辑，再可选聚焦目标元素。
// 切页签原语已拆至 ui/goto-nav.js（工单 ux-walkthrough-02/06 评审整改）：
// settings.js 需要它但没有回边（本模块 import settings 的 expandSettingsCollapse）。
// 设置页定位（工单 ux-polish-02/03）：gotoSettingsKey 补充「先展开 AI API 卡」
// ——key 输入框藏在可折叠的「AI API」卡内，只聚焦不展开会落空；展开原语
// 来自 ui/settings.js（无回边：settings 不 import 本模块）。
import { expandSettingsCollapse } from "/js/ui/settings.js";
import { gotoNavTab } from "/js/ui/goto-nav.js";

export { gotoNavTab } from "/js/ui/goto-nav.js";

/** 去设置页填 key：先展开「AI API」卡（用户手动折叠过也能展开），再切页签 +
 * 聚焦 key 输入框。三个入口共用（欢迎卡 / 生成页横幅 / 设置页横幅）。 */
export function gotoSettingsKey() {
  expandSettingsCollapse("llm-api");
  gotoNavTab("settings", "set-api-key");
}
