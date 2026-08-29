// fx/welcome.js — 首次欢迎卡纯函数（工单 newcomer-onboarding/03）：
// 状态判定单源 welcomeMode（已配 key / 有草稿 / 已选「不再显示」
// → 完整卡 / 精简卡 / 隐藏）+ 卡片 HTML 生成。与渲染解耦：UI 层按
// welcomeMode 结果装配，测试直接驱动纯函数。
import { esc } from "./core.js";

export const WELCOME_DISMISS_KEY = "firstep.welcome-dismissed.v1";

/**
 * 欢迎卡状态判定（单源，spec 决策：欢迎卡=生成页顶部卡片非浮层）。
 * 输入 {apiConfigured, hasDraft, dismissed}，输出 'full' | 'compact' | 'hidden'：
 * - dismissed 已选「不再显示」→ hidden（优先，之后永远不打扰）；
 * - 未配 API key → full（首访新人最重要路径：引导去配 key / 体检）；
 * - 有草稿 → hidden（用户已在干活，不再打扰）；
 * - 已配 key 且无草稿 → compact（一句话鼓励语，低打扰）。
 */
export function welcomeMode({ apiConfigured, hasDraft, dismissed }) {
  if (dismissed) return "hidden";
  if (!apiConfigured) return "full";
  if (hasDraft) return "hidden";
  return "compact";
}

/** 卡片 HTML（mode === 'hidden' 返回空串，由调用方决定隐藏方式）。 */
export function welcomeCardHTML(mode) {
  if (mode === "hidden") return "";
  if (mode === "compact") {
    return '<div class="welcome-line">'
      + esc("贴赛题 → 生成 → 编译 → 上板；12 步向导会带你走每一步。")
      + "</div>";
  }
  return '<div class="welcome-head">'
    + '<div class="welcome-title">' + esc("欢迎使用电赛工程生成器") + "</div>"
    + '<div class="welcome-sub">' + esc("粘贴赛题原文，自动生成「打开就能编译、直接开写」的完整工程（STM32 + Keil5 / MSPM0 + CCS 双平台）。") + "</div>"
    + "</div>"
    + '<ol class="welcome-steps">'
    + '<li>' + esc("配置 AI：右上「设置」页粘贴 DeepSeek API key") + "</li>"
    + '<li>' + esc("检查环境：一键体检 + 补齐参考文件与模块库") + "</li>"
    + '<li>' + esc("粘贴赛题 → 生成 → 编译 → 上板（页面 12 步向导会一路带你走）") + "</li>"
    + "</ol>"
    + '<div class="welcome-actions">'
    + '<button id="btn-welcome-goto-key" type="button" class="accent">去配置 API key</button>'
    + '<button id="btn-welcome-env-check" type="button">检查环境</button>'
    + '<button id="btn-welcome-dismiss" type="button" class="ghost">不再显示</button>'
    + "</div>";
}

if (typeof window !== "undefined") {
  Object.assign(window, { welcomeMode, welcomeCardHTML, WELCOME_DISMISS_KEY });
}
