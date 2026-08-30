// ui/welcome.js — 首次欢迎卡胶水（工单 newcomer-onboarding/03：
// 读状态（api_configured / 草稿 / localStorage 标记）→ welcomeMode
// 判定 → 渲染到 #welcome-card；行动按钮复用既有路径：切设置页签
// （直接触发 nav 按钮点击 = 复用 tab 切换全部既有逻辑，避免重复实现）
// 后聚焦 #set-api-key / 点 #btn-env-check；「不再显示」写 localStorage 即隐藏。
// 跳转归一（工单 beginner-guide/02 评审整改）：gotoSettings 泛化为
// ui/nav-jump.js 的 gotoNavTab，欢迎卡 / gen-banner / 新手指引共用。
// 工单 beginner-guide/04：full 态新增「先看新手指引」按钮 → gotoNavTab("guide")。
import { $, state } from "/js/app.js";
import { draftLoad } from "/js/fx/draft.js";
import { WELCOME_DISMISS_KEY, welcomeMode, welcomeCardHTML } from "/js/fx/welcome.js";
import { gotoNavTab, gotoSettingsKey } from "./nav-jump.js";

export function initWelcome() {
  const slot = $("welcome-card");
  if (!slot) return;
  const mode = welcomeMode({
    apiConfigured: !!state.api_configured,
    hasDraft: !!draftLoad(localStorage),
    dismissed: !!localStorage.getItem(WELCOME_DISMISS_KEY),
  });
  slot.innerHTML = welcomeCardHTML(mode);
  slot.classList.toggle("hidden", mode === "hidden");

  // 欢迎卡行动按钮全部走同一条 gotoNavTab 路径：新增/变更按钮只需加一行
  // （工单 04「先看新手指引」去 guide 页签；其余去配置 key / 体检 / 不再显示）
  $("btn-welcome-guide")?.addEventListener("click", () => gotoNavTab("guide"));
  // 开始做题：切生成页聚焦赛题原文（工单 ux-walkthrough-02/24 compact 态入口）
  $("btn-welcome-compact-go")?.addEventListener("click", () => gotoNavTab("generate", "problem"));
  $("btn-welcome-goto-key")?.addEventListener("click", () => gotoSettingsKey());
  // 生成页「尚未配置 AI API」横幅：去设置也要保证 AI API 卡展开（否则聚焦落空）
  $("btn-banner-goto-settings")?.addEventListener("click", () => gotoSettingsKey());
  // 设置页「尚未配置」横幅（应用设置卡内）：「去填写」走同一条路径
  $("btn-settings-banner-goto")?.addEventListener("click", () => gotoSettingsKey());
  $("btn-welcome-env-check")?.addEventListener("click", () => {
    gotoNavTab("settings");
    $("btn-env-check")?.click();
  });
  $("btn-welcome-dismiss")?.addEventListener("click", () => {
    localStorage.setItem(WELCOME_DISMISS_KEY, "1");
    slot.classList.add("hidden");
    slot.innerHTML = "";
  });
}
