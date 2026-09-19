// fx/hwcheck.js — 硬件检测栏目的纯函数（工单 module-hwcheck/01 + 02）。
//
// 分工（仓库既有约定）：本文件只出字符串与状态对象，**不碰 DOM、不发请求**；
// DOM 胶水全在 ui/hwcheck.js。检测程序本身由后端确定性渲染（零 LLM），
// 前端只负责"选什么、显示什么"，不判规则。esc 单源取自 fx/core.js；
// 工具链展示名单源取自 fx/env.js。
import { esc } from "./core.js";
import { TOOLCHAIN_NAMES } from "./env.js";

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

// hwcheckGenerateErrorHTML(message)：生成失败提示。与预览分开写一句话——
// 生成失败往往是"引擎如实拒绝"（引脚冲突 / 输出父目录不存在 / 还没配置），
// 说成"预览失败"会把用户引到错的地方去查。
export function hwcheckGenerateErrorHTML(message) {
  return `<div class="error">检测工程没有生成成功：${esc(message || "")}</div>`;
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

// ===========================================================================
// 工单 module-hwcheck/02：生成 / 编译降级 / 上板清单 / 最近几次检测
// ===========================================================================

// hwcheckGeneratePayload(state)：生成请求体。与预览请求体的差别只有一处：
// 生成要多带输出**父目录**（空串 = 后端按桌面处理）。
export function hwcheckGeneratePayload(state) {
  return {
    platform: state.platform,
    debug_uart: !!state.debug_uart,
    oled: !!state.oled,
    parent_dir: String(state.parentDir || "").trim(),
  };
}

// hwcheckChecklistKey(outputDir)：勾选态的本地备忘键（**按检测工程目录分**）。
// 一次检测一套勾选：换了工程（重新生成 / 打开另一次检测）就该是另一套。
export function hwcheckChecklistKey(outputDir) {
  return "firstep.hwcheck.checks." + String(outputDir || "");
}

// hwcheckCheckedIds(raw)：localStorage 读回来的勾选态 → id 数组。
// 坏值（null / 非 JSON / 非数组 / 混了非字符串）一律当"一条都没勾"——
// 本地备忘坏了不该让整页报错。
export function hwcheckCheckedIds(raw) {
  if (typeof raw !== "string" || !raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((id) => typeof id === "string");
  } catch {
    return [];
  }
}

// hwcheckChecklistToggle(raw, id, on)：切换一条勾选 → 新的序列化串（写回
// localStorage 用）。纯函数：读串 → 新串，调用方只管存取。
export function hwcheckChecklistToggle(raw, id, on) {
  const ids = hwcheckCheckedIds(raw).filter((x) => x !== id);
  if (on) ids.push(id);
  return JSON.stringify(ids);
}

// hwcheckChecklistHTML(items, checkedIds)：上板清单（应看到什么 / 不对先查哪里）。
// 每项一个勾选框（本地备忘，刷新回显）+ 两行文案；空清单 = 空串（调用方放占位）。
export function hwcheckChecklistHTML(items, checkedIds) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return "";
  const done = new Set(Array.isArray(checkedIds) ? checkedIds : []);
  return list.map((item) => {
    const id = String(item && item.id != null ? item.id : "");
    const checked = done.has(id);
    return `<label class="hwcheck-check${checked ? " done" : ""}">`
      + `<input type="checkbox" data-hwcheck-check="${esc(id)}"${checked ? " checked" : ""}>`
      + '<span class="hwcheck-check-body">'
      + `<span class="hwcheck-check-expect">应看到：${esc((item && item.expect) || "")}</span>`
      + `<span class="hwcheck-check-tip">不对先查：${esc((item && item.check) || "")}</span>`
      + "</span></label>";
  }).join("");
}

// hwcheckChecklistProgressHTML(items, checkedIds)：勾了几条（页面顶上那句）。
export function hwcheckChecklistProgressHTML(items, checkedIds) {
  const total = (Array.isArray(items) ? items : []).length;
  if (!total) return "";
  const done = new Set(Array.isArray(checkedIds) ? checkedIds : []);
  const n = (Array.isArray(items) ? items : []).filter(
    (item) => item && done.has(String(item.id))).length;
  return `<div class="hwcheck-hint">已确认 ${n} / ${total} 条`
    + (n === total ? "——这一趟都对了，可以开始写你的逻辑了。" : "。") + "</div>";
}

// hwcheckProjectState(state, payload)：生成 / 回读成功后的状态更新——把后端载荷
// 归一成一个 project 对象（字段名前后端只在这里对一次，ui 不散读 payload）。
export function hwcheckProjectState(state, payload) {
  const data = payload || {};
  return {
    ...state,
    project: {
      outputDir: String(data.output_dir || ""),
      platform: String(data.platform || ""),
      debugUart: !!data.debug_uart,
      oled: !!data.oled,
      mainC: String(data.main_c || ""),
      outputHint: String(data.output_hint || ""),
      checklist: Array.isArray(data.checklist) ? data.checklist : [],
      modules: Array.isArray(data.modules) ? data.modules : [],
      buildHint: String(data.build_hint || ""),
    },
  };
}

// hwcheckChannelText(project)：通道一句话（面板上给"这次会往哪儿报"）。
export function hwcheckChannelText(project) {
  const uart = !!(project && project.debugUart);
  const oled = !!(project && project.oled);
  if (uart && oled) return "调试串口 + OLED";
  if (uart) return "只有调试串口";
  if (oled) return "只有 OLED";
  return "没有输出通道（只看灯闪）";
}

// hwcheckProjectInfoHTML(project)：工程信息（路径 / 平台 / 通道 / 模块 / 说明）。
export function hwcheckProjectInfoHTML(project, platformLabel) {
  if (!project || !project.outputDir) return "";
  const modules = (project.modules || []).map((slug) => esc(slug)).join("、");
  return `<div class="hwcheck-path">检测工程：<span class="slug">${esc(project.outputDir)}</span></div>`
    + `<div class="hwcheck-hint">平台：${esc(platformLabel || project.platform)}`
    + ` ｜ 输出通道：${esc(hwcheckChannelText(project))}`
    + (modules ? ` ｜ 进工程的模块：${modules}` : "")
    + "</div>"
    + hwcheckHintHTML(project.outputHint);
}

// hwcheckToolchainNote(platform, ready, platformLabel)：编译能力的**大声降级**。
// ready=false 时必须说清"未验证"，不许让用户以为"生成完就验证过了"。
// 工具链展示名走 fx/env.js 的 TOOLCHAIN_NAMES 单源（体检页与这里同一说法）。
export function hwcheckToolchainNote(platform, ready, platformLabel) {
  if (ready) return "";
  const name = TOOLCHAIN_NAMES[platform] || "编译工具链";
  return `<div class="hwcheck-warn">⚠ 本机没探测到 ${esc(name)}：这一趟工程**未经验证**`
    + `（编译这一步做不了，不等于代码有问题）。装好后可到设置页填路径，`
    + `或先按清单上板试——${esc(platformLabel || platform)} 的检测结果只有编译过才算数。</div>`;
}

// hwcheckChannelNoteHTML(platform, debugUart, oled)：**生成之前**就把"这条路会撞脚"
// 说清楚（工单 02 评审整改：spec 用户故事 4「一个器件都不选也能生成」在 mspm0 上
// 默认不成立——地猛星两路的默认脚在原厂例程里是重叠的，生成门禁会如实 400，
// 而检测页原本没有任何引导）。
// 文案刻意**不写具体引脚号**：真正的判据是生成时的门禁（它报的引脚与角色才是权威），
// 这里只是一句"先取消勾选一个"的引导——库内默认脚改了它也不会变成假话。
// 引脚配置 / 接线表与冲突呈现是后续工单（spec 用户故事 3）的事，本单不越界。
export function hwcheckChannelNoteHTML(platform, debugUart, oled) {
  if (platform !== "mspm0" || !debugUart || !oled) return "";
  return '<div class="hwcheck-warn">注意：地猛星（mspm0）上「调试串口 + OLED」这两路的'
    + "默认脚在原厂例程里是重叠的——生成时若报引脚冲突，请先只勾一个通道再生成"
    + "（要两个都用，需要在引脚配置里改绑，检测页暂时做不了）。</div>";
}

// hwcheckActionsHTML(outputDir, opts)：动作行 + 状态位 + 结果容器。
// opts = {compileReady, note}：compileReady=false 时编译按钮置灰（并已由
// hwcheckToolchainNote 说清原因）——按钮不假装能编译。
export function hwcheckActionsHTML(outputDir, opts) {
  if (!outputDir) return "";
  const ready = !opts || opts.compileReady !== false;
  return '<div class="row hwcheck-actions">'
    + `<button class="primary" data-hwcheck-compile="${esc(outputDir)}"${ready ? "" : " disabled"}>编译验证</button>`
    + `<button data-hwcheck-flash="${esc(outputDir)}">烧录到板子</button>`
    + `<button data-hwcheck-open="${esc(outputDir)}"`
    + ' title="stm32 优先拉起 Keil（UV4），兜底打开文件夹；mspm0 打开文件夹（CCS 手动导入）"'
    + ">打开工程</button>"
    + "</div>"
    + '<div id="hwcheck-compile-status" class="code-compile-status"></div>'
    + '<div id="hwcheck-compile-errors"></div>'
    + '<div id="hwcheck-flash-status" class="muted"></div>'
    + '<div id="hwcheck-flash-result"></div>';
}

// hwcheckProjectPanelHTML(project, opts)：工程面板整块（信息 + 动作）。
// project 为空 = 空串（调用方放占位）。
export function hwcheckProjectPanelHTML(project, opts) {
  if (!project || !project.outputDir) return "";
  const o = opts || {};
  return hwcheckProjectInfoHTML(project, o.platformLabel)
    + hwcheckToolchainNote(project.platform, o.compileReady !== false, o.platformLabel)
    + hwcheckActionsHTML(project.outputDir, o)
    + (project.buildHint ? `<div class="hwcheck-hint">${esc(project.buildHint)}</div>` : "");
}

// hwcheckRecentHTML(items, currentDir)：最近几次检测（点一行 = 回读那次检测）。
// currentDir = 当前正在看的工程（高亮，避免"点了没反应"的错觉）。
export function hwcheckRecentHTML(items, currentDir) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return "";
  const current = String(currentDir || "");
  return list.map((item) => {
    const dir = String((item && item.dir) || "");
    const on = dir && dir === current;
    return `<button type="button" class="hwcheck-recent-row${on ? " current" : ""}"`
      + ` data-hwcheck-open-project="${esc(dir)}"`
      + ` title="打开这次检测（路径：${esc(dir)}）">`
      + `<span class="hwcheck-recent-time">${esc((item && item.created_at) || "")}</span>`
      + `<span class="hwcheck-recent-name">${esc((item && item.name) || "")}</span>`
      + `<span class="badge">${esc((item && item.platform) || "")}</span>`
      + (on ? '<span class="badge ok">正在看</span>' : "")
      + "</button>";
  }).join("");
}

// hwcheckRecentEmptyHTML()：一次都没检测过时的占位（不是错误）。
export function hwcheckRecentEmptyHTML() {
  return '<div class="muted">这个输出位置下还没有检测工程。</div>';
}

// hwcheckProjectEmptyHTML()：还没生成时的占位。
export function hwcheckProjectEmptyHTML() {
  return '<div class="empty-state"><div class="es-icon">🧪</div>'
    + '<div class="es-title">还没有检测工程</div>'
    + '<div class="es-hint">选好平台和输出通道后点「生成检测工程」——'
    + '它会新建一个 hwcheck-平台-时间的子目录，编译烧录都在那儿进行，'
    + '不会覆盖你以前生成的任何工程。</div></div>';
}

// 本地备忘键（单源：ui 只经这两个函数读写 localStorage）
export const HWCHECK_PARENT_KEY = "firstep.hwcheck.parentDir";
export const HWCHECK_LAST_DIR_KEY = "firstep.hwcheck.lastDir";

if (typeof window !== "undefined") {
  Object.assign(window, {
    hwcheckPlatformState, hwcheckSelectPlatform, hwcheckPickState,
    hwcheckRequestPayload, hwcheckCanPreview, hwcheckPlatformCardsHTML,
    hwcheckHintHTML, hwcheckErrorHTML, hwcheckGenerateErrorHTML,
    hwcheckEmptyHTML, hwcheckPanelHTML,
    hwcheckCodeTarget, hwcheckPreviewState, hwcheckPlatformLabel,
    HWCHECK_CHANNEL_KEYS,
    hwcheckGeneratePayload, hwcheckChecklistKey, hwcheckCheckedIds,
    hwcheckChecklistToggle, hwcheckChecklistHTML, hwcheckChecklistProgressHTML,
    hwcheckProjectState, hwcheckChannelText, hwcheckProjectInfoHTML,
    hwcheckToolchainNote, hwcheckChannelNoteHTML, hwcheckActionsHTML,
    hwcheckProjectPanelHTML,
    hwcheckRecentHTML, hwcheckRecentEmptyHTML, hwcheckProjectEmptyHTML,
    HWCHECK_PARENT_KEY, HWCHECK_LAST_DIR_KEY,
  });
}

