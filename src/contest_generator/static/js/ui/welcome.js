// ui/welcome.js — 首次欢迎卡胶水（工单 newcomer-onboarding/03）：
// 读状态（api_configured / 草稿 / localStorage 标记）→ welcomeMode
// 判定 → 渲染到 #welcome-card；行动按钮复用既有路径：切设置页签
// （直接触发 nav 按钮点击 = 复用 tab 切换全部既有逻辑，避免重复实现）
// 后聚焦 #set-api-key / 点 #btn-env-check；「不再显示」写 localStorage 即隐藏。
// 跳转归一（工单 beginner-guide/02 评审整改）：gotoSettings 泛化为
// ui/nav-jump.js 的 gotoNavTab，欢迎卡 / gen-banner / 新手指引共用。
import { $, state } from "/js/app.js";
import { draftLoad } from "/js/fx/draft.js";
import { WELCOME_DISMISS_KEY, welcomeMode, welcomeCardHTML } from "/js/fx/welcome.js";
import { gotoNavTab } from "./nav-jump.js";

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

  // 欢迎卡行动按钮与 gen-banner「去设置」共用同一跳转逻辑（去配 key）
  $("btn-welcome-goto-key")?.addEventListener("click", () =>
    gotoNavTab("settings", "set-api-key")
  );
  $("btn-banner-goto-settings")?.addEventListener("click", () =>
    gotoNavTab("settings", "set-api-key")
  );
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
