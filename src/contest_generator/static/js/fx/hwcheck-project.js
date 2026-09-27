// fx/hwcheck-project.js — 硬件检测栏目的纯函数：**生成请求 / 编译降级 / 上板清单 / 最近几次检测 / 工程面板**。
//
// 由 `fx/hwcheck.js` 按职责整段搬来（工单 hwcheck-hygiene/09），**只搬不改**。
// 模块约定与六件的依赖方向见 `fx/hwcheck-state.js` 头部——那份是**单源**，
// 别在这里再抄一遍（抄六遍就是六份会各自漂移的散文）。

import { esc } from "./core.js";
import { TOOLCHAIN_NAMES } from "./env.js";
// 提示壳与器件 slug 归一都在 state（生成载荷要用后者）。
import { hwcheckHintHTML, hwcheckDeviceSlugs } from "./hwcheck-state.js";
// 三个归一器（逐件小节 / 命令台 / 自建件计划）住在 plan：`hwcheckProjectState`
// 把后端载荷一次折成 project 对象，缺谁都不完整。
import {
  hwcheckSectionsState, hwcheckConsoleState, hwcheckCustomState,
} from "./hwcheck-plan.js";

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
  return `<div class="hwcheck-warn">⚠ 本机没探测到 ${esc(name)}：这一趟工程<strong>未经验证</strong>`
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
    + "默认脚在原厂例程里是重叠的。<strong>不用你自己改</strong>——生成检测工程前，检测页会按"
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
// 措辞与 README 的 FAQ 条目、配方数据里那句**同一条规范句**（工单 hwcheck-hardening/09）：
// 「本栏目的配方与探测小节尚未在真板上验证过：现有证据只到「能生成 + 能编译」这一步。」
// 三个落点在三个运行时里（Markdown / JS / JSON 数据），做不到真单源——本仓库的既有做法是
// **刻意同文 + 双端断言**（先例：fix_errors.SYSCFG_CONFLICT_NOTICE 与 syscfgConflictStateText）。
// `tests/test_hwcheck.py::test_unverified_sentence_is_verbatim_the_same_on_page_and_readme` 盯着它：
// 改一处漏一处，用例当场红。
export function hwcheckUnverifiedNoteHTML() {
  return '<div class="hwcheck-warn">⚠ 本栏目的配方与探测小节尚未在真板上验证过：'
    + "现有证据只到「能生成 + 能编译」这一步。"
    + "板上判 FAIL 先按下面的清单查接线；判 OK 也只说明通信走通了，不等于型号对、读数准。</div>";
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
    // 状态行可被读屏念出（工单 hwcheck-hygiene/06）：编译 / 烧录是"要等"的动作，
    // 页面在跑没有不能靠猜。role=status 等价 aria-live="polite"（读屏会在空档里念
    // 变化），不动观感、不加视觉噪音。
    + '<div id="hwcheck-compile-status" class="code-compile-status" role="status"></div>'
    + '<div id="hwcheck-compile-errors"></div>'
    + '<div id="hwcheck-flash-status" class="muted" role="status"></div>'
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

// —— 探针桥（CDP / devtools 与页面内联脚本的既有出口）——
if (typeof window !== "undefined") {
  Object.assign(window, {
    hwcheckGeneratePayload, hwcheckChecklistKey, hwcheckCheckedIds,
    hwcheckChecklistToggle, hwcheckChecklistHTML, hwcheckChecklistProgressHTML,
    hwcheckProjectState, hwcheckChannelText, hwcheckProjectInfoHTML,
    hwcheckToolchainNote, hwcheckChannelNoteHTML, hwcheckActionsHTML,
    hwcheckUnverifiedNoteHTML, hwcheckProjectPanelHTML, hwcheckRecentHTML,
    hwcheckRecentEmptyHTML, hwcheckProjectEmptyHTML, HWCHECK_PARENT_KEY,
    HWCHECK_LAST_DIR_KEY, hwcheckBoardState,
  });
}
