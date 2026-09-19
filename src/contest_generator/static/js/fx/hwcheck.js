// fx/hwcheck.js — 硬件检测栏目的纯函数（工单 module-hwcheck/01）。
//
// 分工（仓库既有约定）：本文件只出字符串与状态对象，**不碰 DOM、不发请求**；
// DOM 胶水全在 ui/hwcheck.js。检测程序本身由后端确定性渲染（零 LLM），
// 前端只负责"选什么、显示什么"，不判规则。esc 单源取自 fx/core.js。
import { esc } from "./core.js";

// —— 栏目内的平台选择状态 ——
// hwcheckPlatformState(platforms, inherited, current)：
//   platforms = GET /api/state 的 platforms（[{id,name,status}]）
//   inherited = 全局当前平台（chosenPlatform，来自生成页）
//   current   = 栏目内已经选过的平台（重进栏目 / 刷新状态时保留）
// 语义：① 重进栏目保留自己的选择；② 没选过则**继承全局当前平台**，但只当
// 该平台"可用"（status=ready，即母版已导入）时才继承；③ 都没有则取第一个
// 可用平台；④ 一个可用的都没有 → 选中 id 为空（页面提示先去导入母版）。
// 这里刻意**只读** platforms 的事实：不要求题面、也不调用生成流程任何状态。
export function hwcheckPlatformState(platforms, inherited, current) {
  const list = Array.isArray(platforms) ? platforms : [];
  const ready = list.filter((p) => p && p.status === "ready");
  const known = new Set(list.map((p) => p && p.id));
  const pick =
    (current && known.has(current) && ready.some((p) => p.id === current) && current) ||
    (inherited && ready.some((p) => p.id === inherited) && inherited) ||
    (ready.length ? ready[0].id : "");
  return { platform: pick || "" };
}

// hwcheckSelectPlatform(state, platform)：点平台卡后的新状态（不可用平台不换）。
// 返回新对象（不改原对象）——纯函数便于单测。
export function hwcheckSelectPlatform(platforms, state, platform) {
  const list = Array.isArray(platforms) ? platforms : [];
  const target = list.find((p) => p && p.id === platform);
  if (!target || target.status !== "ready") return state;
  return { ...state, platform: target.id };
}

// hwcheckPickState(state, key, value)：切换输出通道勾选（debug_uart / oled）。
// 返回新对象；key 不在通道词表内 = 原样返回（防手滑写错键名静默多存一个字段）。
export const HWCHECK_CHANNEL_KEYS = ["debug_uart", "oled"];

export function hwcheckPickState(state, key, value) {
  if (!HWCHECK_CHANNEL_KEYS.includes(key)) return state;
  return { ...state, [key]: !!value };
}

// hwcheckRequestPayload(state)：预览请求体（只有这三个字段——端点不接受
// 题面 / 已选模块：检测程序不依赖生成流程任何状态）。
export function hwcheckRequestPayload(state) {
  return {
    platform: state.platform,
    debug_uart: !!state.debug_uart,
    oled: !!state.oled,
  };
}

// hwcheckCanPreview(state)：平台可用才让点「预览检测程序」（空平台 = 后端必拒）。
export function hwcheckCanPreview(state) {
  return !!(state && state.platform);
}

// hwcheckPlatformCardsHTML(platforms, selected)：平台卡（观感与生成页平台卡
// 一致，独立 DOM 容器 #hwcheck-platforms）；status!==ready 的卡置灰不可点。
export function hwcheckPlatformCardsHTML(platforms, selected) {
  const list = Array.isArray(platforms) ? platforms : [];
  return list.map((p) => {
    const on = p && p.id === selected;
    const disabled = !p || p.status !== "ready";
    const badge = disabled
      ? '<span class="badge no-master">暂不可用：尚未导入母版</span>'
      : '<span class="badge ok">可用</span>';
    return `<div class="platform-card${on ? " selected" : ""}${disabled ? " disabled" : ""}"`
      + ` data-hwcheck-platform="${p ? p.id : ""}" role="button" tabindex="${disabled ? "-1" : "0"}"`
      + ` aria-pressed="${on ? "true" : "false"}"`
      + ` title="${disabled ? "该平台还没导入母版，先去「母版」页导入" : "在本栏目里检测这个平台的板子"}">`
      + `<div class="name">${esc(p ? p.name : "")}</div>${badge}</div>`;
  }).join("");
}

// hwcheckHintHTML(text)：输出通道说明（后端 render_output_hint 给的文案，
// 前端只渲染不判规则）。
export function hwcheckHintHTML(text) {
  return `<div class="hwcheck-hint">${esc(text || "")}</div>`;
}

// hwcheckErrorHTML(message)：预览失败提示（业务 400 的中文理由原样带出）。
export function hwcheckErrorHTML(message) {
  return `<div class="error">检测程序预览失败：${esc(message || "")}</div>`;
}

// hwcheckEmptyHTML(reason)：还没有产物时的占位。
export function hwcheckEmptyHTML(reason) {
  return `<div class="empty-state"><div class="es-icon">🔌</div>`
    + `<div class="es-title">还没有检测程序</div>`
    + `<div class="es-hint">${esc(reason || "")}</div></div>`;
}

// hwcheckPanelHTML(preview, hint)：一次成功预览的产物区——通道说明 + main.c 文本。
// 空预览（还没点过 / 预览清空）= 空串，调用方据此决定放占位还是产物。
// ⚠ 文本本身**不进 HTML**：调用方拿到本串后要把 main.c 用 textContent 写进
// `[data-hwcheck-code]`（见 hwcheckCodeTarget），所以这里只出容器壳。
export function hwcheckPanelHTML(preview, hint) {
  if (!preview) return "";
  return hwcheckHintHTML(hint)
    + `<pre class="result hwcheck-code" data-hwcheck-code></pre>`;
}

// hwcheckCodeTarget(root)：产物区里写 main.c 的容器（壳的唯一出处是
// hwcheckPanelHTML——ui 侧只查询、不再手拼同一段 HTML，防双源漂移）。
export function hwcheckCodeTarget(root) {
  return root ? root.querySelector("[data-hwcheck-code]") : null;
}

// hwcheckPreviewState(state, payload)：预览成功后的状态更新——记下文本与通道
// 说明（下次重绘直接用，不重发请求）。
export function hwcheckPreviewState(state, payload) {
  const data = payload || {};
  return {
    ...state,
    preview: String(data.main_c || ""),
    outputHint: String(data.output_hint || ""),
  };
}

// hwcheckPlatformLabel(platforms, id)：平台展示名（卡片外的文字用；找不到回 id）。
export function hwcheckPlatformLabel(platforms, id) {
  const hit = (Array.isArray(platforms) ? platforms : []).find((p) => p && p.id === id);
  return (hit && hit.name) || String(id || "");
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    hwcheckPlatformState, hwcheckSelectPlatform, hwcheckPickState,
    hwcheckRequestPayload, hwcheckCanPreview, hwcheckPlatformCardsHTML,
    hwcheckHintHTML, hwcheckErrorHTML, hwcheckEmptyHTML, hwcheckPanelHTML,
    hwcheckCodeTarget, hwcheckPreviewState, hwcheckPlatformLabel,
    HWCHECK_CHANNEL_KEYS,
  });
}
