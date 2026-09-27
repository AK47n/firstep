// fx/hwcheck-state.js — 硬件检测栏目的纯函数：**状态归一 / 请求载荷 / 平台卡 / 提示与错误文案**。
//
// 模块约定（**单源**；改这里就够，其余五件只转引本段）：
// 由 `fx/hwcheck.js` 按职责整段搬来（工单 hwcheck-hygiene/09），**只搬不改**——函数体与注释
// 逐字保留，唯一的增量是文件头说明与 import 段。分工照旧（仓库既有约定）：只出字符串与
// 状态对象，**不碰 DOM、不发请求**；DOM 胶水全在 ui/hwcheck.js；加载顺序无关——六件只声明、
// 不在求值期做任何事。依赖方向（单向，无环）：state / plan / wiring / triage 是叶子；
// project → state + plan；handoff → state。window 桥条目由各件发布自己那一段（并集与搬前
// 逐名相同，由 tests/js/hwcheck-split-integrity.test.mjs 钉住）。

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

// hwcheckRequestPayload(state)：预览请求体（平台 / 两个通道 / 选中的器件——
// 端点不接受题面 / 已选模块：检测程序不依赖生成流程任何状态）。
export function hwcheckRequestPayload(state) {
  return {
    platform: state.platform,
    debug_uart: !!state.debug_uart,
    oled: !!state.oled,
    devices: hwcheckDeviceSlugs(state),
  };
}

// hwcheckDeviceSlugs(state)：选中的器件 slug 数组（去重保序，空 = 一件都没选）。
// 载荷里只出 slug——器件对象由服务端从模块库现读（前端不把自己那份缓存当判据）。
export function hwcheckDeviceSlugs(state) {
  const list = (state && Array.isArray(state.devices)) ? state.devices : [];
  const out = [];
  list.forEach((slug) => {
    const key = String(slug == null ? "" : slug);
    if (key && !out.includes(key)) out.push(key);
  });
  return out;
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

// hwcheckGenerateErrorHTML(message)：生成失败提示。与预览分开写一句话——
// 生成失败往往是"引擎如实拒绝"（引脚冲突 / 输出父目录不存在 / 还没配置），
// 说成"预览失败"会把用户引到错的地方去查。
export function hwcheckGenerateErrorHTML(message) {
  return `<div class="error">检测工程没有生成成功：${esc(message || "")}</div>`;
}

// hwcheckDroppedNoteHTML(dropped)：选择集里那些**已经从器件库消失**的自建件说明
// （工单 ci-gate-fixes/09）。
//
// 为什么要有它：用户会走这条路——选上自己的器件 → 回「我的器件」把它删了 → 再回来
// 预览。服务端现在把这种"已经不在库里"的件**从这次检测里摘掉**（不摘就是整页
// 400「库中不存在模块：mine_xxx」，那句话还指错了地方：`mine_*` 从来不是库内模块），
// 摘掉就必须**说出来**——不然页面上少了一件，用户只看到"我明明选着它"。
// 空清单 / 缺字段（旧载荷）→ 空串，与从前逐字节一致。
export function hwcheckDroppedNoteHTML(dropped) {
  const slots = Array.isArray(dropped) ? dropped.filter(Boolean).map(String) : [];
  if (!slots.length) return "";
  return slots.map((slug) =>
    `<div class="hwcheck-dropped-note">「${esc(slug)}」已经不在你的器件里了`
    + `——这次检测已把它摘掉（要留着它就回「我的器件」重新登记，再选上）。</div>`
  ).join("");
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

// —— 探针桥（CDP / devtools 与页面内联脚本的既有出口）——
if (typeof window !== "undefined") {
  Object.assign(window, {
    hwcheckPlatformState, hwcheckSelectPlatform, hwcheckPickState,
    hwcheckRequestPayload, hwcheckCanPreview, hwcheckPlatformCardsHTML,
    hwcheckHintHTML, hwcheckErrorHTML, hwcheckGenerateErrorHTML,
    hwcheckDroppedNoteHTML, hwcheckEmptyHTML, hwcheckPanelHTML,
    hwcheckCodeTarget, hwcheckPreviewState, hwcheckPlatformLabel,
    HWCHECK_CHANNEL_KEYS, hwcheckDeviceSlugs,
  });
}
