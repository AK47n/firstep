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
    ...hwcheckCustomState(state, data),
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

// hwcheckChannelNoteHTML(platform, debugUart, oled)：**生成之前**就把"这两路默认撞脚"
// 说清楚（工单 02 评审整改：spec 用户故事 4「一个器件都不选也能生成」在 mspm0 上
// 默认不成立）。
// 工单 hwcheck-pin-conflict-exit/01 起这句话**变了性质**：默认撞脚由检测页在生成前
// 自动解开（`hwcheck_pin_plan`，与赛题页「自动配置」同一个求解器），所以这里不再教
// 「先只勾一个通道」——那是把母版布局的账算到学生头上；现在说的是"会自动移开、
// 移了哪几根请看下面的接线表与提示"。撞的是哪几个脚仍由接线表与同脚组逐条列出。
export function hwcheckChannelNoteHTML(platform, debugUart, oled) {
  if (platform !== "mspm0" || !debugUart || !oled) return "";
  return '<div class="hwcheck-warn">注意：地猛星（mspm0）上「调试串口 + OLED」这两路的'
    + "默认脚在原厂例程里是重叠的。**不用你自己改**——生成检测工程前，检测页会按"
    + "同一套判据自动把它移开（移了哪几根见下面接线表上方的提示，接线表已经是新脚）。"
    + "若这套器件组合真的装不下（板子脚不够），页面会点明是哪几件、建议去掉哪一件。</div>";
}

// hwcheckUnverifiedNoteHTML()：全栏目的**总口径**（工单 hwcheck-hardening/02）。
//
// 为什么必须有这一句：库内所有配方与探测小节**都还没在真板上跑过**（`library/modules/*/manifest.json`
// 里 170 条「未上板」是同一件事）。各格自己的平台说明里虽然逐格写着「未上板」，但
//   ① 学生不一定读到某一格的说明；② 页面上没有任何一句话交代"整块能力"的分量。
// 于是"板上判 FAIL"很容易被读成"我的线接错了/器件坏了"，而检测页的设计前提恰恰是
// 「检测没过 = 正常结果，先自查接线」——那就更需要先告诉他这个前提。
//
// 措辞与配方数据里那句**同源**（同一个事实、两种粒度），别在这里另编一种说法。
export function hwcheckUnverifiedNoteHTML() {
  return '<div class="hwcheck-warn">⚠ 本栏目的配方与探测小节尚未在真板上验证过：'
    + "现有证据只到「能生成 + 能编译」。板上判 FAIL 先按下面的清单查接线；"
    + "判 OK 也只说明通信走通了，不等于型号对、读数准。</div>";
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

// hwcheckPinFixHTML(pinFixes)：生成前**自动移开的默认脚撞脚**（工单
// hwcheck-pin-conflict-exit/01）。为什么必须明说：检测页没有引脚配置入口，学生
// 照"原厂默认脚"接好线却生成了另一组脚，是最难查的一类不一致——所以页面把动过的
// 每一根线原样打出来（说明行由服务端给，前端只渲染），并点明接线表已是新脚。
// 空数组 = 这一趟一根都没动，不渲染任何东西（不制造"好像出过事"的错觉）。
export function hwcheckPinFixHTML(pinFixes) {
  const list = (Array.isArray(pinFixes) ? pinFixes : []).map((item) => String(item || ""))
    .filter((item) => item);
  if (!list.length) return "";
  return '<div class="hwcheck-warn">⚠ 生成前自动移开了 '
    + `${list.length} 处默认脚冲突（这几根线**不按原厂默认脚**，按下面接线表接）：`
    + list.map((item) => `<div class="hwcheck-pin-fix">· ${esc(item)}</div>`).join("")
    + "</div>";
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
//
// 自建件那几行（工单 hwcheck-unknown-device/05）**排在库内之后**（服务端拼好，
// 这里不重排）：多两个服务端字段——`tag_text`（标注词「自建件：按你确认的事实
// 探测」，与库内 `[专精]` 严格区分）与 `name`（slug 之外给人认的那个名字）。
export function hwcheckOrderHTML(order, guide, reason) {
  const list = Array.isArray(order) ? order : [];
  if (!list.length) return "";
  const items = list.map((item, index) => {
    const one = item || {};
    const tag = one.bring_up ? '<span class="badge ok">先做·板子活着</span>' : "";
    const custom = one.custom
      ? (one.tag_text ? `<span class="badge custom">${esc(one.tag_text)}</span>` : "")
        + (one.name ? `<span class="hwcheck-order-name">${esc(one.name)}</span>` : "")
      : "";
    return '<li class="hwcheck-order-row">'
      + `<span class="hwcheck-order-index">${index + 1}</span>`
      + `<span class="slug">${esc(one.slug || "")}</span>${tag}${custom}`
      + `<span class="hwcheck-order-desc">${esc(hwcheckOrderDesc(one.description))}</span>`
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

// hwcheckUnspecializedHTML(items)：没配方的器件 → **通用降级小节**（工单 07）。
//
// 这一版它们真出小节了（只做初始化 +（I2C 类件）总线地址扫描），所以页面不能再
// 说"不会给它出检测小节"（04 那句已经过期）。三件事都**只渲染服务端给的字**：
// `label`（官方的「未专精：…」标注，单源）、`plan`（这一趟对它做什么）、
// `message`（点名那句完整话）——前端一个字都不另写，也不给缺字段编兜底句
// （缺 label 就不画那个徽章；编一句就是同一句话两处写、迟早两种措辞）。
//
// **外观可区分**（票面验收线）：专精件是实心 `[专精]` 徽章 + 判定档位，通用件是
// 描边 `◻` + 「不算通过」——学生一眼能看出哪些结论可信、哪些只是走了个过场
// （spec 用户故事 10）。
//
// ⚠ 容器类名**不是** `.hwcheck-section`：那个类是"专精小节"的选择器（页面、
// 浏览器验收与静态守卫都按它数"这一趟真测了几件"），通用件套上它会让那个数
// 数不清（真机验收当场抓到：`sectionCount` 从 1 变 2）。通用件用
// `.hwcheck-generic`，只复用结构性的 `.hwcheck-section-head` / `.hwcheck-section-tag`
// （那是"节的头 / 节的徽章"，与专精与否无关）。
export function hwcheckUnspecializedHTML(items) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return "";
  const rows = list.map((item) => {
    const one = item || {};
    const label = String(one.label || "");
    const plan = String(one.plan || "");
    const message = String(one.message || one.slug || "");
    const tag = label
      ? `<span class="hwcheck-section-tag generic">◻ ${esc(label)}</span>`
      : "";
    return '<div class="hwcheck-generic">'
      + '<div class="hwcheck-section-head">'
      + tag
      + `<span class="slug">${esc(one.slug || "")}</span>`
      + '<span class="badge">不算通过</span></div>'
      + (plan ? `<div class="hwcheck-hint">这一节：${esc(plan)}</div>` : "")
      + `<div class="hwcheck-hint">${esc(message)}</div>`
      + "</div>";
  }).join("");
  return '<div class="hwcheck-hint">下面这几件没有专精配方，走通用降级'
    + "——板上判不了通断，所以它们<strong>不算通过</strong>"
    + "（每件这一趟到底做了什么，逐条列在下面）：</div>" + rows;
}

// hwcheckSectionsEmptyHTML()：一件专精件都没有时的说明。
// **不是错误状态**：不选器件 = 「先确认板子活着」那条路（spec 用户故事 4）；
// 选了器件但都没配方时，它们由 hwcheckUnspecializedHTML 逐条点名**并且真的
// 出通用小节**（工单 07）——这里说清"为什么这条是空的"，不留一块沉默的空白。
export function hwcheckSectionsEmptyHTML() {
  return '<div class="muted">这一趟没有专精件：检测程序会跑 LED 心跳 + 通道自报，'
    + "选中的器件走通用降级（只验总线和初始化，见下一条）。"
    + "专精小节来自库内配方——服务端按库内配方给，页面不猜哪几件有。</div>";
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
// 有串口：命令逐条列出（敲什么 / 哪一件 / 测什么）+ 既有 r/y/g/o/b 单列
// + 帮助字符。**没有串口就不摆那张表**——摆出来像"敲了就行"，而这一趟根本
// 没有命令循环（服务端那句 hint 会明说不能交互式复测，票面要求）。
//
// 自建件那几行（工单 hwcheck-unknown-device/06）：字符是服务端分配的，页面
// **只渲染**；多出来的两个键（`tag` 标注词 / `name` 人读名）判据全在服务端，
// 这里按"有没有 `tag`"分两种画法——缺字段 = 库内件（与 fx/module.js 那处
// "旧载荷无字段 = 保守按库内件"同一条口径）。前端不判"哪个字符是谁的"。
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
    const name = String(one.name || "");
    const tag = String(one.tag || "");
    // 「哪一件」那一格：自建件带名称与标注词——名字与后端 `ConsoleEntry.label`
    // 同一个意思（跨语言读同一个词），库内件就是 slug。
    const label = tag
      ? `<span class="slug">${esc(one.slug || "")}</span>`
        + (name ? ` <span class="hwcheck-custom-name">${esc(name)}</span>` : "")
        + ` <span class="badge custom">${esc(tag)}</span>`
      : esc(one.slug || "");
    return '<tr><td class="hwcheck-pin">' + esc(one.command || "") + "</td>"
      + `<td>${label}</td>`
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

// ===========================================================================
// 工单 module-hwcheck/08：现象回填 + AI 排障（本栏目唯一的 LLM 入口）
//
// 分工照旧：**判据全在服务端**——事实约束（引脚名 / 模块名必须来自本次检测
// 上下文）与兜底文案都在 `hwcheck_triage` 域层，前端只做两件事：把"页面现在
// 的现象与勾选"装配成请求体、把服务端给的建议渲染成 HTML。前端不判建议对不对
// （那会变成第二个判据来源）。
// ===========================================================================

// 定性标签的兜底文案（服务端 verdict_label 缺失时才用；正常情况用服务端的）
const HWCHECK_VERDICT_FALLBACK = "先按下面的线索查";

// hwcheckSymptomText(state)：学生填的现象（去首尾空白；空串 = 还不能提交）。
export function hwcheckSymptomText(state) {
  return String((state && state.symptom) || "").trim();
}

// hwcheckCanTriage(state)：有检测工程 + 填了现象，才让点「让 AI 分析」。
// 没工程时后端必拒（400 目录不存在），这里是"按钮别让人白点"。
export function hwcheckCanTriage(state) {
  const dir = String((state && state.project && state.project.outputDir) || "");
  return !!dir && !!hwcheckSymptomText(state);
}

// hwcheckTriagePayload(state)：排障请求体（工程目录 / 现象 / 当前勾选）。
// 勾选随请求走（与页面上显示的是同一份）——服务端据此落盘，刷新后回显。
export function hwcheckTriagePayload(state) {
  return {
    output_dir: String((state && state.project && state.project.outputDir) || ""),
    symptom: hwcheckSymptomText(state),
    checked_ids: (state && Array.isArray(state.checklistChecked))
      ? state.checklistChecked.slice()
      : [],
  };
}

// hwcheckChecklistPayload(state)：勾选落盘请求体（零 LLM 的轻端点）。
export function hwcheckChecklistPayload(state) {
  return {
    output_dir: String((state && state.project && state.project.outputDir) || ""),
    checked_ids: (state && Array.isArray(state.checklistChecked))
      ? state.checklistChecked.slice()
      : [],
  };
}

// hwcheckAdviceState(state, payload)：排障响应 → 建议面板状态。
// 载荷缺 advice = 保留当前面板（出错响应不许把上一次的建议抹掉）；失败的
// 原因（message）单独存一个键——它是"为什么这次是兜底"，不是建议正文。
export function hwcheckAdviceState(state, payload) {
  const data = payload || {};
  const advice = (data.advice && typeof data.advice === "object") ? data.advice : null;
  if (!advice) {
    return {
      advice: (state && state.advice) || null,
      adviceMessage: String(data.message || (state && state.adviceMessage) || ""),
      adviceDegraded: !!(data.degraded || (state && state.adviceDegraded)),
    };
  }
  return {
    advice,
    adviceMessage: String(data.message || ""),
    adviceDegraded: !!data.degraded,
    triageError: "",
  };
}

// hwcheckRecordState(state, payload)：工程回读载荷里的检测记录 → 状态。
// 载荷没有 record 键（preview / generate 不带它）= 不动现状；有记录时把
// 现象 / 勾选 / 建议一起回显（刷新后"我上次填了什么、它说了什么"还在）。
export function hwcheckRecordState(state, payload) {
  const data = payload || {};
  const record = (data.record && typeof data.record === "object") ? data.record : null;
  if (!record) return {};
  const advice = (record.advice && typeof record.advice === "object") ? record.advice : null;
  return {
    symptom: String(record.symptom || ""),
    checklistChecked: Array.isArray(record.checked_ids)
      ? record.checked_ids.filter((id) => typeof id === "string")
      : [],
    advice,
    adviceMessage: "",
    adviceDegraded: !!(advice && advice.degraded),
  };
}

// hwcheckChecklistState(state, payload)：勾选落盘端点的响应 → 只更新勾选。
// **只认 checked_ids**（工单 08 评审整改）：这个端点的响应里也带着记录里的
// 现象与建议，整份采纳会把用户"还没提交的现象"覆盖成服务端旧值——下一页
// 提交时那句原话就丢了。现象的真源是输入框，建议的真源是排障端点。
export function hwcheckChecklistState(state, payload) {
  const data = payload || {};
  const record = (data.record && typeof data.record === "object") ? data.record : null;
  if (!record || !Array.isArray(record.checked_ids)) return {};
  return {
    checklistChecked: record.checked_ids.filter((id) => typeof id === "string"),
  };
}

// hwcheckTriageErrorHTML(message)：排障请求本身失败（网络 / 400）的提示。
// 与"模型失败"分开说：模型失败是 200 + 兜底建议，"请求失败"才是这一段。
export function hwcheckTriageErrorHTML(message) {
  return `<div class="error">AI 排障没能提交：${esc(message || "")}</div>`;
}

// hwcheckAdviceEmptyHTML()：还没分析过 / 还没生成工程时的占位。
export function hwcheckAdviceEmptyHTML() {
  return '<div class="hwcheck-hint">跑完一遍之后，把上面「实际现象」填进来，'
    + "点「让 AI 分析」——它会先说这更像接线、器件还是程序的问题，再给下一步查什么。"
    + "检测没过是正常结果，不用怕填。</div>";
}

// hwcheckAdviceHTML(advice)：建议面板 = 定性 + 一句话判断 + 可能原因 +
// 下一步查什么 + 反馈出口；`degraded` 那份明说"这是兜底文案、可重试"，
// 不把它当模型结论（票面：LLM 失败不阻断）。
export function hwcheckAdviceHTML(advice) {
  const data = (advice && typeof advice === "object") ? advice : null;
  if (!data) return hwcheckAdviceEmptyHTML();
  const degraded = !!data.degraded;
  const label = String(data.verdict_label || HWCHECK_VERDICT_FALLBACK);
  const causes = (Array.isArray(data.causes) ? data.causes : [])
    .filter((item) => typeof item === "string" && item.trim());
  const steps = (Array.isArray(data.steps) ? data.steps : [])
    .filter((item) => typeof item === "string" && item.trim());
  const summary = String(data.summary || "");
  const issue = String(data.issue_hint || "");
  const blocks = [];
  if (causes.length) {
    blocks.push('<div class="hwcheck-advice-block">'
      + '<div class="hwcheck-advice-title">可能原因</div><ul>'
      + causes.map((item) => `<li>${esc(item)}</li>`).join("") + "</ul></div>");
  }
  if (steps.length) {
    blocks.push('<div class="hwcheck-advice-block">'
      + '<div class="hwcheck-advice-title">下一步查什么</div><ol>'
      + steps.map((item) => `<li>${esc(item)}</li>`).join("") + "</ol></div>");
  }
  return `<div class="hwcheck-advice${degraded ? " degraded" : ""}">`
    + '<div class="hwcheck-advice-head">'
    + `<span class="hwcheck-advice-verdict">${esc(label)}</span>`
    + (degraded
      ? '<span class="badge no-master">兜底文案（AI 这次没给出来，可以重试）</span>'
      : "")
    + "</div>"
    + (summary ? `<div class="hwcheck-advice-summary">${esc(summary)}</div>` : "")
    + blocks.join("")
    + (issue ? `<div class="hwcheck-hint">${esc(issue)}</div>` : "")
    + "</div>";
}

// ===========================================================================
// 工单 hwcheck-unknown-device/05：自建件的**检测计划**（接线行 / 标注 / 为什么
// 没有它的探测小节）
//
// 分工不变：标注词（「自建件：按你确认的事实探测」）、接线那一行（名称 + 地址 +
// 支点那对脚）、"这一趟对它做什么"——**全部来自服务端载荷**（`hwcheck_custom`
// 单源），本文件一个字都不另写。尤其**不在这里判"这件的总线是不是 I2C"**：
// 那是"出不出探测小节"的判据，服务端已经判过一次（`probes`），前端再判一次就是
// 两处各说各话——页面上说会测、产物里没有它。
// ===========================================================================

// hwcheckCustomState(state, payload)：载荷里的"自建件计划"部分。
// 载荷缺键 = 保留当前状态（旧后端 / 出错响应不许把已有的计划抹掉）。
// 同样只返回自己的键（见 hwcheckBoardState 的 spread 说明）。
export function hwcheckCustomState(state, payload) {
  const data = payload || {};
  return {
    custom: Array.isArray(data.custom)
      ? data.custom
      : ((state && Array.isArray(state.custom)) ? state.custom : []),
  };
}

// hwcheckCustomPlanHTML(items)：自建件的检测计划面板。
//
// **空 = 空串**：一件自建件都没有时检测页逐字与改动前一致（票面第 6 条）。
// 出小节的件与不出小节的件**都画**（后者把"为什么没有它的探测程序"原样带出来）
// ——只画前者就是一次悄无声息的少测。
//
// 外观与库内 `.hwcheck-section` 刻意不同（自己的类名 + 服务端给的标注词）：
// 学生要一眼看出哪些结论是库内验证过的、哪些只是"按我给的地址试了一下"。
export function hwcheckCustomPlanHTML(items) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return "";
  const rows = list.map((item) => {
    const one = item || {};
    const facts = [
      one.address_text ? `地址 ${esc(one.address_text)}` : "",
      one.register_text ? `身份寄存器 ${esc(one.register_text)}` : "",
      one.expect_text ? `期望值 ${esc(one.expect_text)}` : "",
    ].filter(Boolean).join(" ｜ ");
    const tag = one.tag_text
      ? `<span class="hwcheck-section-tag custom">${esc(one.tag_text)}</span>`
      : "";
    const badge = one.probes
      ? '<span class="badge ok">板上判定</span>'
      : '<span class="badge">这一趟没有它的探测小节</span>';
    // 快照出处（工单 hwcheck-unknown-device/08）：回读以工程内快照为准——
    // 行上如实标"来自我的器件 <id>"；那条已被删掉时再补一句（不静默、不报错）。
    // 现读行（预览 / 08 之前的工程）不画标记。
    const source = one.snapshot
      ? `<div class="hwcheck-hint hwcheck-custom-snapshot">来自我的器件 ${esc(one.slug || "")} `
        + (one.stored
          ? "</div>"
          : "（这一条已从「我的器件」删除——这里显示的是工程内快照）</div>")
      : "";
    return `<div class="hwcheck-custom-plan" data-custom-plan="${esc(one.slug || "")}">`
      + '<div class="hwcheck-section-head">'
      + tag
      + `<span class="slug">${esc(one.slug || "")}</span>`
      + `<span class="hwcheck-custom-name">${esc(one.name || "")}</span>${badge}</div>`
      + (facts ? `<div class="hwcheck-hint">${facts}</div>` : "")
      + `<div class="hwcheck-hint">这一趟对它做什么：${esc(one.plan || "")}</div>`
      + (one.notes ? `<div class="hwcheck-hint">你填的备注：${esc(one.notes)}</div>` : "")
      + source
      + "</div>";
  }).join("");
  return rows;
}

// hwcheckCustomWiringHTML(items)：接线区里自建件那一行（服务端算好的整句）。
//
// 只画**有接线说明**的那几件（`wiring_text` 非空 = 这一趟真借了支点那条总线）：
// 没有它就没有线可接，编一行出来等于让学生去找一根不存在的线。
export function hwcheckCustomWiringHTML(items) {
  const list = (Array.isArray(items) ? items : []).filter(
    (item) => item && item.wiring_text);
  if (!list.length) return "";
  return list.map((item) =>
    `<div class="hwcheck-custom-wiring" data-custom-wiring="${esc(item.slug || "")}">`
    + `<span class="hwcheck-section-tag custom">${esc(item.tag_text || "")}</span>`
    + esc(item.wiring_text) + "</div>").join("");
}

// ===========================================================================
// 工单 hwcheck-acceptance/04：检测页 → 生成页的衔接（只带器件，不带引脚）
//
// 页面上的一个动作：把**当前选中的库内器件**并进生成页的已选清单——学生在检测页
// 验通一件之后不用回生成页再找一遍同名模块。三条判据都在本文件（纯函数，数组 /
// 字符串进出，零 DOM 零请求），因为它们是"该不该进生成载荷"的判据：
//   ① **只带库内件**：「我的器件」（库外自建件）**不走生成链**——它没有 manifest、
//      不进 slugs，生成链上游（`resolve_dependencies`）会直接拒；带过去等于把
//      一个必然 400 的 slug 塞进载荷。
//   ② **逐个过库内词表**：不在词表里的 slug 一件都不许带（"点了没反应"与"生成时
//      才 400"两种分家都从这一处杜绝），并逐件给出中文理由。
//   ③ **引脚不带**：检测页没有引脚配置入口，而生成前自动移开的那几根线是**这一页
//      的本地裁决**（不是用户做出的选择）——带过去就是把没做过的决定塞进生成页。
//      页面上必须自己把这条说清楚（学生照着检测页的接线表接好线，却以为生成页
//      会用同一组脚，是最难查的一类不一致）。
//
// **"库外件"的判据不写成 id 前缀**（`mine_`）：前缀是 `my_devices.DEVICE_ID_PATTERN`
// 的事，页面再判一遍就是第二份实现（改了文法两处必然分叉）。这里判的是"它在不在
// 自建件清单里"——清单来自服务端载荷。
// ===========================================================================

// hwcheckHandoffPlan(devices, librarySlugs, myDevices)：把选中的器件分成三类。
//   devices      = 当前选中的 slug（去重保序，与请求载荷同一个取法）
//   librarySlugs = 库内 slug 词表（模块库真源）
//   myDevices    = 「我的器件」清单（[{id, name}]，服务端载荷）
// → { carry: [slug…], custom: [{id, name}…], unknown: [slug…] }
// 分类**先判词表**：slug 同时在两处时按"库内"算（生成链认的是词表；自建件撞库内
// slug 在保存那一步就被服务端拒了，这条只是把顺序钉死，不留两种答案）。
export function hwcheckHandoffPlan(devices, librarySlugs, myDevices) {
  const known = new Set(
    (Array.isArray(librarySlugs) ? librarySlugs : [])
      .map((slug) => String(slug == null ? "" : slug)).filter(Boolean));
  const mine = new Map();
  (Array.isArray(myDevices) ? myDevices : []).forEach((item) => {
    const id = String((item && item.id) || "");
    if (id) mine.set(id, String((item && item.name) || ""));
  });
  const carry = []; const custom = []; const unknown = [];
  hwcheckDeviceSlugs({ devices }).forEach((slug) => {
    if (known.has(slug)) carry.push(slug);
    else if (mine.has(slug)) custom.push({ id: slug, name: mine.get(slug) });
    else unknown.push(slug);
  });
  return { carry, custom, unknown };
}

// hwcheckHandoffMerge(selected, carry)：把要带的几件**并进**生成页的已选清单。
// → { selected: […], added: […], already: […] }
//
// 生成页那侧的 selectedSlugs 由推荐簇 A 持有（唯一写者），本函数只算"并进去之后
// 长什么样"——于是"不重复加、保持原顺序、已选过的如实报 already"这三条规则可直测，
// ui 侧只剩写状态 + 重绘（双轴评审整改：原来那条 ui 断言在数 runExpand() 出现几次，
// 那是实现细节，不是行为）。
export function hwcheckHandoffMerge(selected, carry) {
  const out = (Array.isArray(selected) ? selected : [])
    .map((slug) => String(slug == null ? "" : slug)).filter(Boolean);
  // `already` 的判据 = **本来就在生成页里**，所以拿入参那份快照比——不能拿边算边长的
  // out 比：入参里重复出现的同一件会被算成"本来就在"，那是句假话。
  const base = new Set(out);
  const added = []; const already = [];
  (Array.isArray(carry) ? carry : []).forEach((slug) => {
    const key = String(slug == null ? "" : slug);
    if (!key) return;
    if (base.has(key)) {
      if (!already.includes(key)) already.push(key);
      return;
    }
    if (out.includes(key)) return;   // 入参里重复的一件：只加一次，也不假报 already
    out.push(key);
    added.push(key);
  });
  return { selected: out, added, already };
}

// hwcheckHandoffPinNote()：**引脚那一句的唯一出处**——带入块里那句与带过去之后
// 回报那句同源（两处各写一句必然分叉；先例见 fx/my-devices.js 文件头的「文案单源」）。
export function hwcheckHandoffPinNote() {
  return "只带器件、不带引脚（引脚到生成页第 7 步再配）";
}

// hwcheckHandoffResultText(added, already)：带过去之后那一句回报（ui 只把它塞进
// toast，不自己拼文案）。两段都可能为空（第二次点同一批 = added 空、already 满），
// 但引脚那一句**恒在**——"带过去的东西里没有引脚"这件事每次都要说。
export function hwcheckHandoffResultText(added, already) {
  const add = (Array.isArray(added) ? added : []).filter(Boolean);
  const had = (Array.isArray(already) ? already : []).filter(Boolean);
  const parts = [];
  if (add.length) parts.push("已带进生成页 " + add.length + " 件：" + add.join("、"));
  if (had.length) parts.push("另有 " + had.length + " 件本来就在工程里：" + had.join("、"));
  parts.push(hwcheckHandoffPinNote());
  return parts.join("；");
}

// hwcheckHandoffHTML(plan, opts)：带入块（说明 + 一个按钮）。
//
// opts = {
//   pinFixes:  这一趟生成前自动移开的默认脚冲突处数（wiring.pin_fixes 的长度；
//              0 = 还没取到接线表 / 一根都没动——两种都不许说成"没出过事"）
//   platforms: 平台清单（GET /api/state 那份；只用来取展示名）
//   from / to：检测页选的平台 / 生成页当前的平台（不一致时提前讲明）
// }
//
// 按钮**没有可带的东西时置灰**（而不是点下去没反应）：理由就写在同一块里。
// 逐条理由的形状（三种都不静默）：带过去几件 / 自建件为什么不带 / 词表外为什么拒收。
export function hwcheckHandoffHTML(plan, opts = {}) {
  const one = plan || {};
  const carry = Array.isArray(one.carry) ? one.carry : [];
  const custom = Array.isArray(one.custom) ? one.custom : [];
  const unknown = Array.isArray(one.unknown) ? one.unknown : [];
  const pinFixes = Number(opts.pinFixes) > 0 ? Number(opts.pinFixes) : 0;
  const platforms = Array.isArray(opts.platforms) ? opts.platforms : [];
  const rows = [];

  // ① 引脚那一句：**永远在**（这是这一栏与生成页之间唯一说不清的地方）。
  //    开头就是 `hwcheckHandoffPinNote()` 那一句（单源，块里与回报那句共用）；
  //    "自动消解的那几根也不带过去、那不是你的选择"这一条同样**恒在**——接线表
  //    还没取到时我们并不知道移开过几根，但"移开过的也不带"这句话永远为真。
  rows.push('<div class="hwcheck-hint">' + hwcheckHandoffPinNote()
    + "：检测页没有引脚配置，不动就按默认布线。"
    + (pinFixes
      ? `这一趟生成前自动移开了 ${pinFixes} 处默认脚冲突，那几根也不带过去：`
        + "那是检测页的自动消解，不是你的选择。"
      : "检测页为避开冲突自动移开的线（如果有）同样不带过去："
        + "那是这一页的自动消解，不是你的选择。")
    + "</div>");

  // ② 要带过去的（空 = 说清"还没有可带的"，不让人对着灰按钮猜）
  if (carry.length) {
    rows.push('<div class="hwcheck-hint">要带过去 '
      + `<strong>${carry.length}</strong> 件：`
      + carry.map((slug) => `<span class="slug">${esc(slug)}</span>`).join("、")
      + "（生成页里已选过的不会重复加）</div>");
  } else if (!custom.length && !unknown.length) {
    rows.push('<div class="muted">还没选器件——先在上面选一件库内器件，'
      + "这里就能把它带进生成页（省得回去再找一遍同名模块）。</div>");
  } else {
    rows.push('<div class="muted">选中的这几件都带不过去——原因见下。</div>');
  }

  // ③ 库外自建件：为什么不带（点名是哪一件，学生才知道说的是他那件）
  custom.forEach((item) => {
    rows.push('<div class="hwcheck-hint">不带「' + esc(item.name || item.id)
      + '」（<span class="slug">' + esc(item.id) + '</span>）：库外自建件不在模块库里'
      + "——没有 manifest、不进 slugs，生成链不认它。要进工程，先在「模块库」把它"
      + "补录成模块。</div>");
  });

  // ④ 两类清单都没有这一件：**两个成因都说**（清单没读到 / 确实删了），不武断地
  //    只说后者——两份清单各自读失败时都是空集，那时"它已经被删了"是句假话。
  unknown.forEach((slug) => {
    rows.push('<div class="hwcheck-warn">⚠ <span class="slug">' + esc(slug)
      + "</span> 没有带过去：它现在既不在模块库清单里、也不在「我的器件」里"
      + "（可能是这两份清单有一份没读出来——刷新一次再看；也可能这件确实已经删了）。"
      + "生成链只认库内模块，硬塞进去只会在生成时被拒。</div>");
  });

  // ⑤ 平台不一致（两个栏目各选各的平台）：带过去之后按**生成页**的平台校验，
  //    这一句只是把"那边为什么会说它不支持"提前讲明（不替用户切平台）。
  const from = String(opts.from || "");
  const to = String(opts.to || "");
  if (from && to && from !== to) {
    rows.push('<div class="hwcheck-warn">⚠ 检测页选的是「'
      + esc(hwcheckPlatformLabel(platforms, from)) + "」，生成页当前是「"
      + esc(hwcheckPlatformLabel(platforms, to))
      + "」——带过去后按生成页的平台校验（那边不支持的模块会在第 6 步列出来）。</div>");
  }

  const label = carry.length
    ? `把这 ${carry.length} 件带进生成页`
    : "带进生成页";
  return '<div class="hwcheck-handoff">'
    + `<button data-hwcheck-handoff${carry.length ? "" : " disabled"}>${label}</button>`
    + rows.join("") + "</div>";
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    hwcheckPlatformState, hwcheckSelectPlatform, hwcheckPickState,
    hwcheckRequestPayload, hwcheckCanPreview, hwcheckPlatformCardsHTML,
    hwcheckHintHTML, hwcheckErrorHTML, hwcheckGenerateErrorHTML,
    hwcheckDroppedNoteHTML,
    hwcheckEmptyHTML, hwcheckPanelHTML,
    hwcheckCodeTarget, hwcheckPreviewState, hwcheckPlatformLabel,
    HWCHECK_CHANNEL_KEYS,
    hwcheckGeneratePayload, hwcheckChecklistKey, hwcheckCheckedIds,
    hwcheckChecklistToggle, hwcheckChecklistHTML, hwcheckChecklistProgressHTML,
    hwcheckProjectState, hwcheckChannelText, hwcheckProjectInfoHTML,
    hwcheckToolchainNote, hwcheckChannelNoteHTML, hwcheckActionsHTML,
    hwcheckUnverifiedNoteHTML,
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
    hwcheckSymptomText, hwcheckCanTriage, hwcheckTriagePayload,
    hwcheckChecklistPayload, hwcheckAdviceState, hwcheckRecordState,
    hwcheckChecklistState,
    hwcheckTriageErrorHTML, hwcheckAdviceHTML, hwcheckAdviceEmptyHTML,
    HWCHECK_VERDICT_FALLBACK,
    hwcheckCustomState, hwcheckCustomPlanHTML, hwcheckCustomWiringHTML,
    hwcheckHandoffPlan, hwcheckHandoffHTML, hwcheckHandoffMerge,
    hwcheckHandoffPinNote, hwcheckHandoffResultText,
  });
}

