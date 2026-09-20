// fx/hwcheck.js — 硬件检测栏目的纯函数（工单 module-hwcheck/01 + 02）。
//
// 分工（仓库既有约定）：本文件只出字符串与状态对象，**不碰 DOM、不发请求**；
// DOM 胶水全在 ui/hwcheck.js。检测程序本身由后端确定性渲染（零 LLM），
// 前端只负责"选什么、显示什么"，不判规则。esc 单源取自 fx/core.js；
// 工具链展示名单源取自 fx/env.js。
import { esc } from "./core.js";
import { TOOLCHAIN_NAMES } from "./env.js";
// chip 渲染取自模块库既有纯件（工单 03：器件选择复用既有载荷与卡片/chip 渲染，
// 不另造一套模块清单协议）。
import { recommendChipHTML } from "./module.js";

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
    devices: hwcheckDeviceSlugs(state),
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

// hwcheckBoardState(state, payload)：一次响应里的「板侧」部分——器件回显 +
// 接线视图 + 同组互斥组（preview 与 generate / 回读三个端点都带这几项）。载荷
// 缺键 = 保留当前状态（旧后端 / 出错响应不许把用户刚选的器件抹掉）。
//
// ⚠ 只返回**自己那几个键**，不 `...state` 展开：`hwcheckProjectState` 把几个
// 归一器叠在一起（`{...a, ...b, ...c}`），谁展开旧 state，谁就把前一个刚更新的
// 键按旧值覆盖回去（评审实测的 spread 顺序回归：回读一次，器件与检测计划退回
// 上一次的值）。"缺键保留"由每个字段各自的 `state.x` 回退负责，不需要整份 state。
export function hwcheckBoardState(state, payload) {
  const data = payload || {};
  return {
    devices: Array.isArray(data.devices)
      ? data.devices.map((slug) => String(slug))
      : (Array.isArray(state && state.devices) ? state.devices : []),
    wiring: (data.wiring && typeof data.wiring === "object")
      ? data.wiring
      : ((state && state.wiring) || null),
    exclusiveGroups: Array.isArray(data.exclusive_groups)
      ? data.exclusive_groups
      : ((state && Array.isArray(state.exclusiveGroups)) ? state.exclusiveGroups : []),
  };
}

// hwcheckProjectState(state, payload)：生成 / 回读成功后的状态更新——把后端载荷
// 归一成一个 project 对象（字段名前后端只在这里对一次，ui 不散读 payload）。
export function hwcheckProjectState(state, payload) {
  const data = payload || {};
  return {
    ...hwcheckBoardState(state, data),
    ...hwcheckSectionsState(state, data),
    ...hwcheckConsoleState(state, data),
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
// 工单 03 起这句话**不再自称判据**：撞的是哪几个脚由接线表与冲突预警（服务端
// 同脚组）逐条列出，这里只说"生成时还报冲突怎么办"这条出路——硬编码的
// 平台专属说法与真判据并列会变成两个口径。
export function hwcheckChannelNoteHTML(platform, debugUart, oled) {
  if (platform !== "mspm0" || !debugUart || !oled) return "";
  return '<div class="hwcheck-warn">注意：地猛星（mspm0）上「调试串口 + OLED」这两路的'
    + "默认脚在原厂例程里是重叠的——下面的接线表与冲突预警会把撞在一起的脚逐条"
    + "列出来。生成时若报引脚冲突，请先只勾一个通道再生成"
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

// ===========================================================================
// 工单 module-hwcheck/03：器件选择 + 接线表 + 默认脚冲突预警 + 建议顺序
//
// 分工不变：判据全在服务端（接线行 = 生成工程 README 同一推导；共享 / 冲突 =
// 既有同脚分类；顺序 = 既有 bring-up 前置排序），本文件只把载荷渲染成 HTML 与
// 维护选择态。**不在这里判冲突、不在这里推顺序**——两处各推一遍必然漂移。
// ===========================================================================

// hwcheckSameExclusiveGroup(groups, a, b)：a 与 b 是不是**同一个互斥组**的成员。
// 判据只吃服务端给的组（库内 manifest 的 exclusive_group 投影，判据单源在
// `collect_exclusive_groups`）——前端不自己推组、也不写 slug 名单。
function hwcheckSameExclusiveGroup(groups, a, b) {
  const x = String(a == null ? "" : a);
  const y = String(b == null ? "" : b);
  if (!x || !y || x === y) return false;
  return (Array.isArray(groups) ? groups : []).some((group) => {
    const members = (group && group.members) || [];
    return members.includes(x) && members.includes(y);
  });
}

// hwcheckDevicePick(state, slug, on, groups)：选中 / 取消一件器件 → 新状态。
//
// **同组互斥 = 单选交换**（工单 05 用户拍板，与 fx/module.js 的组卡「单选交换」
// 同规则）：点开一件属于某互斥组的器件时，把**同组已选的其它成员**一并去掉——
// 这一组只能选一件（如姿态类 imu_uart / jy61p / ml_mpu6050）。组清单由服务端
// 按平台过滤后下发（单成员组不出，与赛题侧生成链路同一函数）。
//
// 取消（on=false）不做交换：去掉一件不会让另一件变得可选。
// 返回新对象（不改原对象）；空 slug / 状态本来就是这样 = 原样返回（幂等——
// 重复点同一件不该把它挪到列表末尾，那会顺带改变"器件在建议顺序里的位置"）。
export function hwcheckDevicePick(state, slug, on, groups = []) {
  const current = Array.isArray(state && state.devices) ? state.devices : [];
  const key = String(slug == null ? "" : slug);
  if (!key) return state;
  const has = current.includes(key);
  if (has === !!on) return state;
  let next = current.filter((item) => item !== key);
  if (on) {
    next = next.filter((item) => !hwcheckSameExclusiveGroup(groups, key, item));
    next.push(key);
  }
  return { ...state, devices: next };
}

// hwcheckDeviceGroupNoticeHTML(groups, devices)：同组互斥的页面提示。
//
// 两种情形分开说（都不静默）：
//   * 选中的组内成员 **≥2** —— 点选那条路已经收了，这里只可能是回读 / 历史态
//     留下的（后端换过组定义等），如实报"只能选一件，请去掉一件再生成"；
//   * 组内**已选一件**且还有别的成员 —— 明说"再点 X 会自动换掉 Y"，把单选
//     交换这条规则摆到台面上（用户点之前就知道会发生什么，不被静默换掉）。
export function hwcheckDeviceGroupNoticeHTML(groups, devices) {
  const list = Array.isArray(groups) ? groups : [];
  const sel = (Array.isArray(devices) ? devices : []).map((slug) => String(slug));
  const rows = [];
  (list || []).forEach((group) => {
    const members = ((group && group.members) || []).map((slug) => String(slug));
    const chosen = members.filter((slug) => sel.includes(slug));
    if (!chosen.length) return;
    const label = esc(String((group && group.label) || (group && group.id) || ""));
    if (chosen.length >= 2) {
      rows.push('<div class="hwcheck-warn">⚠ 同组互斥（' + label + '）：'
        + esc(chosen.join(" × ")) + " 只能选一件——请去掉一件再生成。</div>");
      return;
    }
    const others = members.filter((slug) => !sel.includes(slug));
    if (!others.length) return;
    rows.push('<div class="hwcheck-hint">▸ 同组互斥（' + label + '）：这一组只能选一件'
      + "——再点 " + esc(others.join(" / ")) + " 会自动换掉 " + esc(chosen[0]) + "。</div>");
  });
  return rows.join("");
}

// hwcheckDevicePool(modules)：可挑选的器件池 = **模块库全量**（/api/modules 既有
// 载荷，与模块库页 / 生成页同一份，卡片渲染也同一套）。
//
// 为什么**不按 kind 过滤**（工单 03 评审整改）：`library.MODULE_KIND` 分的是
// 「要不要购买链接」，不是「能不能上板测」。按它过滤会把 spec 的 v1 专精清单里的
// `adc`（internal，却有 ADC 引脚声明）关在门外——检测页会永远选不到它。挑选面
// 的收敛留给配方与专精标注（后续工单），这里一个字都不判。
export function hwcheckDevicePool(modules) {
  return (Array.isArray(modules) ? modules : []).filter((m) => m && m.slug);
}

// hwcheckDeviceKit(modules, slug, platform)：已选器件的套件型号（chip 上那句
// 小字）——取 /api/modules 载荷里该平台条目的 kit（人补的硬件身份字段）；
// 没有 = 空串（不编造）。
export function hwcheckDeviceKit(modules, slug, platform) {
  const hit = (Array.isArray(modules) ? modules : []).find((m) => m && m.slug === slug);
  const entry = hit && hit.platforms ? hit.platforms[platform] : null;
  return String((entry && entry.kit) || "");
}

// hwcheckDeviceChipsHTML(devices, modules, platform)：已选器件 chips。
// **复用推荐区的 chip 渲染**（fx/module.js recommendChipHTML：绿底 + ✕「点击
// 从工程里移除」+ 内嵌「说明」按钮）——不另造一套卡片协议；点 chip = 把这一件
// 从这次检测的工程里去掉（说明按钮由 ui 用既有 bindModuleInfoEntry 委托拦住）。
export function hwcheckDeviceChipsHTML(devices, modules, platform) {
  const list = (Array.isArray(devices) ? devices : []).filter(Boolean);
  if (!list.length) return "";
  return list.map((slug) => recommendChipHTML(
    slug, hwcheckDeviceKit(modules, slug, platform), true)).join("");
}

// hwcheckDeviceEmptyHTML()：一件器件都没选时的说明（这不是错误状态——
// 「先确认板子活着」本来就是检测页的第一条路）。
export function hwcheckDeviceEmptyHTML() {
  return '<div class="muted">还没选器件——也可以就这样生成：那是先确认板子和'
    + '烧录链路是好的（灯在闪 = 程序在跑）。选上器件后，下面会出现它们的接线表、'
    + '默认脚冲突与建议检测顺序。</div>';
}

// hwcheckMissingDevicesHTML(missing)：选了**本平台没有条目**的器件 → 逐条点名
// （票面硬要求：不静默省略——悄悄从接线表里消失会让学生以为"选上了、能测"）。
export function hwcheckMissingDevicesHTML(missing) {
  const list = Array.isArray(missing) ? missing : [];
  if (!list.length) return "";
  return list.map((item) => {
    const text = (item && (item.message || item.slug)) || "";
    return `<div class="hwcheck-warn">⚠ ${esc(text)}</div>`;
  }).join("");
}

// hwcheckWiringErrorHTML(message)：接线表取不到时的提示。与"预览失败"分开写一句
// ——取不到表的原因（模块库没配好 / 库外 slug）跟"检测程序渲染失败"是两回事，
// 说成一句会把用户引到错的地方去查。
export function hwcheckWiringErrorHTML(message) {
  return `<div class="error">接线表与冲突暂时取不到：${esc(message || "")}</div>`;
}

// hwcheckWiringTableHTML(rows, footnote)：接线表（列与工程 README「引脚接线表」
// 同序：模块 / 角色 / 引脚 / 说明）。pin_note = 板上共享注记（如地猛星 PA0/PA1 的
// 「板载 LED 共用」）——挂在同一行上：学生照着表和板子对线时才看得见这条暗雷。
// footnote = 与工程 README 同一句尾注（服务端随载荷下发；空 = 不渲染）。
export function hwcheckWiringTableHTML(rows, footnote) {
  const list = Array.isArray(rows) ? rows : [];
  const tail = footnote
    ? `<div class="hwcheck-hint">${esc(footnote)}</div>` : "";
  if (!list.length) {
    return '<div class="muted">这次没有已声明引脚角色的接线行——所选模块的实现'
      + "内嵌母版（如 stm32 的 led / delay），不产生独立接线。</div>" + tail;
  }
  const body = list.map((row) => {
    const note = String((row && row.pin_note) || "").trim();
    return "<tr>"
      + `<td><span class="slug">${esc((row && row.slug) || "")}</span></td>`
      + `<td>${esc((row && (row.role || row.role_id)) || "")}</td>`
      + `<td><span class="hwcheck-pin">${esc((row && row.pin) || "")}</span></td>`
      + `<td>${esc((row && row.remark) || "")}`
      + (note ? `<span class="hwcheck-share">⚠ 板载共享：${esc(note)}</span>` : "")
      + "</td></tr>";
  }).join("");
  return '<table class="hwcheck-table"><thead><tr>'
    + "<th>模块</th><th>角色</th><th>引脚</th><th>说明</th>"
    + `</tr></thead><tbody>${body}</tbody></table>`
    + '<div class="hwcheck-hint">这张表与生成出来的工程 README「引脚接线表」'
    + "是同一份推导（同一函数、同一字段）——照着它插线就行。</div>"
    + tail;
}

// hwcheckRoleLabeler(rows)：同脚组里的角色键（`<slug>.<role_id>`，服务端既有
// 角色键文法）→ 显示文本（`slug·角色`，角色取接线表里那一行的渲染文本）。
// 找不到对应行 = 原样显示角色键（不猜、不丢——它仍是真实存在的角色）。
function hwcheckRoleLabeler(rows) {
  const by = new Map();
  (Array.isArray(rows) ? rows : []).forEach((row) => {
    if (row && row.slug && row.role_id) {
      by.set(row.slug + "." + row.role_id, String(row.role || row.role_id));
    }
  });
  return (key) => {
    const text = String(key == null ? "" : key);
    const role = by.get(text);
    if (!role) return esc(text);
    return esc(text.split(".")[0] + "·" + role);
  };
}

// hwcheckBoardSharesHTML(board_shares, rows)：**板上自带**的共享脚（板定义里写了
// 注记的脚，如地猛星 PA0/PA1「板载 LED 共用」）。与模块之间的同脚组分开列：
// 这类重叠不是"你选错了"，是板子本来就这么接的——但学生必须知道（灯会跟着串口
// 通信微闪、I2C 上拉靠模块板自带），所以不能只藏在接线表的说明列里。
export function hwcheckBoardSharesHTML(boardShares, rows) {
  const list = Array.isArray(boardShares) ? boardShares : [];
  if (!list.length) return "";
  const label = hwcheckRoleLabeler(rows);
  return '<div class="hwcheck-hint">板上自带的共享（原厂就这么接的，不是接线错误）：</div>'
    + list.map((item) => {
      const roles = ((item && item.roles) || []).map(label).join(" × ");
      return '<div class="hwcheck-group board-share">'
        + '<span class="hwcheck-group-mark">⚠ 板上共享</span>'
        + `<span class="hwcheck-pin">${esc((item && item.pin) || "")}</span>`
        + `<span class="hwcheck-group-roles">${roles}</span>`
        + `<span class="hwcheck-group-reason">${esc((item && item.note) || "")}</span>`
        + "</div>";
    }).join("");
}

// hwcheckPinGroupsHTML(groups, rows)：模块之间的同脚组 → **物理冲突（⚠）/
// 合法共享（✓）**。kind / reason 全部来自服务端既有同脚分类（同一 I2C 总线 =
// 可共享；同脚分属不同外设 = 物理不通）；前端只上色，不改判。
// 空集那句话必须**说准**：`_shared_groups` 只看模块角色，看不见板上自带的共享
// （板载 LED / 板载上拉），所以不能写成"没有共用同一个引脚"——那是假安心
// （工单 03 评审整改）。板载共享由 hwcheckBoardSharesHTML 单独列。
export function hwcheckPinGroupsHTML(groups, rows) {
  const list = Array.isArray(groups) ? groups : [];
  if (!list.length) {
    return '<div class="hwcheck-ok">✓ 没有两件模块抢同一个引脚'
      + "（板上自带的共享另见下一条）。</div>";
  }
  const label = hwcheckRoleLabeler(rows);
  return list.map((group) => {
    const conflict = (group && group.kind) === "conflict";
    const roles = ((group && group.roles) || []).map(label).join(" × ");
    return `<div class="hwcheck-group ${conflict ? "conflict" : "share"}">`
      + `<span class="hwcheck-group-mark">${conflict ? "⚠ 引脚冲突" : "✓ 可共享"}</span>`
      + `<span class="hwcheck-pin">${esc((group && group.pin) || "")}</span>`
      + `<span class="hwcheck-group-roles">${roles}</span>`
      + `<span class="hwcheck-group-reason">${esc((group && group.reason) || "")}</span>`
      + "</div>";
  }).join("");
}

// hwcheckOrderDesc(text)：顺序行里的简介截断——顺序表是给人**扫一眼**的清单，
// 不是读简介的地方（库内简介常有整段）。切点与推荐区「瘦身行」同一取舍：先找
// 「。」再找「；」取更早的那个，再按字符上限兜底加省略号。
const HWCHECK_ORDER_DESC_CHARS = 60;

export function hwcheckOrderDesc(text) {
  const raw = String(text == null ? "" : text).trim();
  if (!raw) return "";
  const stops = ["。", "；"].map((mark) => raw.indexOf(mark)).filter((i) => i >= 0);
  let out = stops.length ? raw.slice(0, Math.min(...stops) + 1) : raw;
  if (out.length > HWCHECK_ORDER_DESC_CHARS) {
    out = out.slice(0, HWCHECK_ORDER_DESC_CHARS) + "…";
  }
  return out;
}

// hwcheckOrderHTML(order, guide, reason)：建议检测顺序（bring-up 前置，判据 =
// 服务端既有排序；`bring_up` 标记同源）。空集 = 空串（调用方放占位）。
export function hwcheckOrderHTML(order, guide, reason) {
  const list = Array.isArray(order) ? order : [];
  if (!list.length) return "";
  const items = list.map((item, index) => {
    const tag = item && item.bring_up ? '<span class="badge ok">先做·板子活着</span>' : "";
    return '<li class="hwcheck-order-row">'
      + `<span class="hwcheck-order-index">${index + 1}</span>`
      + `<span class="slug">${esc((item && item.slug) || "")}</span>${tag}`
      + `<span class="hwcheck-order-desc">${esc(hwcheckOrderDesc(item && item.description))}</span>`
      + "</li>";
  }).join("");
  return `<div class="hwcheck-hint">${esc(guide || "")}</div>`
    + `<ol class="hwcheck-order">${items}</ol>`
    + `<div class="hwcheck-hint">为什么是这个次序：${esc(reason || "")}</div>`;
}

// ===========================================================================
// 工单 module-hwcheck/04：这一趟**真测哪几件**（配方驱动的小节）+ 未专精点名
//
// 分工不变：配方与判据全在服务端（`GET/POST /api/hwcheck/*` 的 `sections` /
// `unspecialized`），本文件只把载荷渲染成 HTML。**不在这里判"这件测不测得了"**
// ——那会变成第二个判据来源，与后端的配方表迟早对不上。
// ===========================================================================

// hwcheckSectionsState(state, payload)：载荷里的"逐件小节 + 未专精点名"部分。
// 载荷缺键 = 保留当前状态（旧后端 / 出错响应不许把已有的检测计划抹掉）。
// 同样只返回自己的键（见 hwcheckBoardState 的 spread 说明）。
export function hwcheckSectionsState(state, payload) {
  const data = payload || {};
  return {
    sections: Array.isArray(data.sections)
      ? data.sections
      : ((state && Array.isArray(state.sections)) ? state.sections : []),
    unspecialized: Array.isArray(data.unspecialized)
      ? data.unspecialized
      : ((state && Array.isArray(state.unspecialized)) ? state.unspecialized : []),
  };
}

// hwcheckSectionPlanText(section)：一节"到底测什么"的一句话。
// 判定档位由服务端事实决定（有探头 / 只有初始化返回值 / 只做动作不判定）——
// 前端只选词，不改判：把"看着测了其实没测"如实说成"只看现象"。
export function hwcheckSectionPlanText(section) {
  const s = section || {};
  const probe = s.probe && typeof s.probe === "object" ? s.probe : null;
  const parts = [];
  if (probe && probe.expect) {
    parts.push(`通信探头带判定（期望 ${probe.expect}）`);
  } else if (probe) {
    parts.push("探头只做动作、板上不做判定");
  }
  if (s.init_expect) parts.push(`初始化返回值判定（期望 ${s.init_expect}）`);
  else if ((s.init || []).length) parts.push("初始化（不判返回值）");
  if ((s.read || []).length) parts.push(`${s.read.length} 项读数回显`);
  if (s.console) parts.push(`串口命令 ${s.console.command}`);
  return parts.length ? parts.join(" ｜ ") : "这一节没有实际动作";
}

// hwcheckSectionNoteHTML(section)：平台差异说明（直接印出来，不折叠）。
// 规格要求"平台不对称如实呈现"——地猛星没有浮点显示接口、通道被钳回 0 这类
// 事实写在配方的 note 里，学生看检测页就该看到，不该翻 manifest。
export function hwcheckSectionNoteHTML(section) {
  const notes = ((section && section.note) || []).filter(Boolean);
  if (!notes.length) return "";
  return notes.map((line) => `<div class="hwcheck-hint">▸ ${esc(line)}</div>`).join("");
}

// hwcheckSectionsHTML(sections)：逐件专精小节清单。
// **外观可区分**（票面验收线）：专精件带 [专精] 徽章（服务端给的 tag），
// 未专精件根本不在这里（由 hwcheckUnspecializedHTML 单独点名）。
export function hwcheckSectionsHTML(sections) {
  const list = Array.isArray(sections) ? sections : [];
  if (!list.length) return "";
  const rows = list.map((item) => {
    const s = item || {};
    const tag = esc(s.tag || "[专精]");
    const probeBadge = s.has_probe
      ? '<span class="badge ok">板上判定</span>'
      : '<span class="badge">只看现象</span>';
    return '<div class="hwcheck-section">'
      + '<div class="hwcheck-section-head">'
      + `<span class="hwcheck-section-tag">${tag}</span>`
      + `<span class="slug">${esc(s.slug || "")}</span>${probeBadge}</div>`
      + `<div class="hwcheck-hint">这一节：${esc(hwcheckSectionPlanText(s))}</div>`
      + hwcheckSectionNoteHTML(s)
      + "</div>";
  }).join("");
  return '<div class="hwcheck-hint">这一趟的检测程序会给下面这几件出专精小节'
    + "（配方来自库内数据，不是 AI 写的）：</div>" + rows;
}

// hwcheckUnspecializedHTML(items)：选了但没有配方的器件 → **逐条点名**。
// 不做通用降级的这一版必须说清"这一趟不会真测它"（spec「不假装测过」），
// 不许它静默消失在检测清单里。
export function hwcheckUnspecializedHTML(items) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return "";
  return list.map((item) => {
    const text = (item && (item.message || item.slug)) || "";
    return `<div class="hwcheck-warn">◻ ${esc(text)}</div>`;
  }).join("");
}

// hwcheckSectionsEmptyHTML()：一件专精件都没有时的说明。
// **不是错误状态**：不选器件 = 「先确认板子活着」那条路（spec 用户故事 4）；
// 选了器件但都没配方由 hwcheckUnspecializedHTML 逐条点名。这里只要说清
// "为什么这条是空的"，不留一块沉默的空白。
export function hwcheckSectionsEmptyHTML() {
  return '<div class="muted">这一趟没有专精件：检测程序只有 LED 心跳 + 通道自报，'
    + "用来确认板子和烧录链路是好的。选上有配方的器件就会出现它们的检测小节"
    + "（服务端按库内配方给，页面不猜哪几件有）。</div>";
}

// ===========================================================================
// 工单 module-hwcheck/06：串口命令台（复测不用重烧）
//
// 分工照旧：命令表由服务端从库内配方生成（`console_payload`），本文件只把
// 载荷渲染成 HTML。**不在这里判"哪个字符是谁的"**——判重与保留字都在服务端
// （两件抢字符 = 构建期 400），前端再判一次就是第二个判据来源。
// ===========================================================================

// hwcheckConsoleState(state, payload)：载荷里的"串口命令台"部分。
// 载荷缺键 = 保留当前状态（旧后端 / 出错响应不许把已有的命令表抹掉）。
// 同样只返回自己的键（见 hwcheckBoardState 的 spread 说明）。
export function hwcheckConsoleState(state, payload) {
  const data = payload || {};
  const next = data.console;
  return {
    console: (next && typeof next === "object")
      ? next
      : ((state && state.console) || null),
  };
}

// hwcheckConsoleHTML(console)：命令台面板。
// 有串口：配方命令逐条列出（敲什么 / 哪一件 / 测什么）+ 既有 r/y/g/o/b 单列
// + 帮助字符。**没有串口就不摆那张表**——摆出来像"敲了就行"，而这一趟根本
// 没有命令循环（服务端那句 hint 会明说不能交互式复测，票面要求）。
export function hwcheckConsoleHTML(console) {
  const data = (console && typeof console === "object") ? console : null;
  if (!data) return "";
  const hint = String(data.hint || "");
  const help = String(data.help_command || "?");
  const commands = Array.isArray(data.commands) ? data.commands : [];
  const legacy = Array.isArray(data.legacy) ? data.legacy : [];
  if (!hint && !commands.length && !legacy.length) return "";
  if (data.available === false) {
    return hint ? `<div class="hwcheck-hint">${esc(hint)}</div>` : "";
  }
  const rows = commands.map((item) => {
    const one = item || {};
    return '<tr><td class="hwcheck-pin">' + esc(one.command || "") + "</td>"
      + `<td>${esc(one.slug || "")}</td>`
      // 说明由服务端恒填（缺省句的后端单源是 ConsoleEntry.detail）：前端不另写
      // 一句兜底，否则同一句文案两处写、迟早两种措辞。
      + `<td>${esc(one.description || "")}</td></tr>`;
  }).join("");
  const table = rows
    ? '<table class="hwcheck-table"><thead><tr><th>敲这个</th><th>哪一件</th>'
      + "<th>复测什么</th></tr></thead><tbody>" + rows + "</tbody></table>"
    : "";
  const legacyLine = legacy.length
    ? '<div class="hwcheck-hint">既有命令（库内 debug_cmd_poll 执行，'
      + "语义没变）："
      + legacy.map((item) => esc((item || {}).command || "") + " "
        + esc((item || {}).description || "")).join(" / ")
      + "</div>"
    : "";
  return '<div class="hwcheck-console">'
    + (hint ? `<div class="hwcheck-hint">${esc(hint)}</div>` : "")
    + table + legacyLine
    + `<div class="hwcheck-hint">帮助：敲 `
    + `<span class="hwcheck-pin">${esc(help)}</span> 列出全部命令。</div>`
    + "</div>";
}

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
    hwcheckDevicePick, hwcheckDevicePool, hwcheckDeviceKit,
    hwcheckDeviceChipsHTML, hwcheckDeviceEmptyHTML, hwcheckMissingDevicesHTML,
    hwcheckDeviceGroupNoticeHTML,
    hwcheckWiringErrorHTML, hwcheckWiringTableHTML, hwcheckPinGroupsHTML,
    hwcheckBoardSharesHTML, hwcheckOrderHTML, hwcheckOrderDesc,
    hwcheckDeviceSlugs, hwcheckBoardState,
    hwcheckSectionsState, hwcheckSectionsHTML, hwcheckUnspecializedHTML,
    hwcheckSectionsEmptyHTML, hwcheckSectionPlanText, hwcheckSectionNoteHTML,
    hwcheckConsoleState, hwcheckConsoleHTML,
  });
}

