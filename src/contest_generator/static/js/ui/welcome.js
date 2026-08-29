// ui/welcome.js — 首次欢迎卡胶水（工单 newcomer-onboarding/03）：
// 读状态（api_configured / 草稿 / localStorage 标记）→ welcomeMode
// 判定 → 渲染到 #welcome-card；行动按钮复用既有路径：切设置页签
// （直接触发 nav 按钮点击 = 复用 tab 切换全部既有逻辑，避免重复实现）
// 后聚焦 #set-api-key / 点 #btn-env-check；「不再显示」写 localStorage 即隐藏。
import { $, state } from "/js/app.js";
import { draftLoad } from "/js/fx/draft.js";
import { WELCOME_DISMISS_KEY, welcomeMode, welcomeCardHTML } from "/js/fx/welcome.js";

// 共享跳转（工单 03 决策#4 gotoSettings(tab, focusId?)）：切到指定页签
// （直接触发 nav 按钮点击 = 复用 tab 切换全部既有逻辑）+ 可选聚焦元素。
// 欢迎卡「去配置 API key」、gen-banner「去设置」、「检查环境」三条路径
// 都经此归一，不各自内联重写。
function gotoSettings(tab, focusId) {
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
    gotoSettings("settings", "set-api-key")
  );
  $("btn-banner-goto-settings")?.addEventListener("click", () =>
    gotoSettings("settings", "set-api-key")
  );
  $("btn-welcome-env-check")?.addEventListener("click", () => {
    gotoSettings("settings");
    $("btn-env-check")?.click();
  });
  $("btn-welcome-dismiss")?.addEventListener("click", () => {
    localStorage.setItem(WELCOME_DISMISS_KEY, "1");
    slot.classList.add("hidden");
    slot.innerHTML = "";
  });
}
