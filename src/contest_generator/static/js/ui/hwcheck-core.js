// ui/hwcheck-core.js — 硬件检测栏目的**核心渲染件**（工单 hwcheck-hygiene/11）：
// 栏目状态 + 各区块渲染 + 面板编排。正文由 `ui/hwcheck.js`（1401 行）整段搬来，
// **函数体与注释逐字保留**——唯一的增量是文件头、import 段与一个写入口
// `setPendingFocus`（跨件写不了 `let`，见它自己的注释）。
//
// ## 四件与单向依赖（**单源**；改这里就够，另三件只转引本段）
//
//   ui/hwcheck.js          入口：**对外**（`boot.js` 与用例）只有两个导出
//                          （renderHwcheckPanel / initHwcheck）＋ 全部事件委托接线
//                          （处理分支下沉到下面两件）。其余三件的导出是**件间**接口，
//                          不是对外契约。
//   ui/hwcheck-devices.js  「我的器件」（库外件）的增删改查与草稿
//   ui/hwcheck-actions.js  动作与请求（预览 / 生成 / 采纳 / 恢复 / 编译 / 烧录 /
//                          清单同步 / 排障提交 / 带入生成页）
//   ui/hwcheck-core.js     本件：状态 + 各区块渲染（含面板编排 renderHwcheckPanel）
//
// 依赖方向（**单向、无环**；由 tests/js/ui-cycle.test.mjs 与静态对账守卫守）。真实边是
// 四组并列，**不是**一条链——按本段读，别按"入口 → 器件 → 动作 → 核心"那样读成一条链：
//
//     入口 → 器件 / 动作 / 核心      三件并列，入口可以用其中任何一件
//     器件 → 动作 / 核心             删掉一件后要重取板侧视图，所以够得着动作
//     动作 → 核心
//     核心 → 谁都不 import           只 import fx / app
//
// 面板编排（renderHwcheckPanel）住在本件、它要调的那块「我的器件」列表渲染
// （renderMyDevices）也一并留在这里——否则就是"核心 → 器件"的反向边。反过来的
// 代价是「我的器件」那一块**渲染在核心件、增删改查在器件件**：分成两件的依据是
// "谁调得到谁"，不是"看上去像不像一类东西"。
//
// 为什么这条方向要写死：入口一度是 1401 行里八类职责混住，每次改动都要重新建立上下文。
// 反向边一旦出现，那个大文件会以另一种形状长回来，而 `ui-cycle` 只拦得住成环的那一种。
// **不许用 window 桥绕过**（工单 hwcheck-hygiene/01 已把"模块正文靠全局桥解析"判死）。

import { $, state } from "/js/app.js";
import { hwcheckHandoffHTML, hwcheckHandoffPlan } from "/js/fx/hwcheck-handoff.js";
import {
  hwcheckConsoleHTML,
  hwcheckConsoleNoteHTML,
  hwcheckCustomPlanHTML,
  hwcheckCustomWiringHTML,
  hwcheckSectionsEmptyHTML,
  hwcheckSectionsHTML,
  hwcheckUnspecializedHTML,
} from "/js/fx/hwcheck-plan.js";
import {
  hwcheckChannelNoteHTML,
  hwcheckChecklistHTML,
  hwcheckChecklistProgressHTML,
  hwcheckProjectEmptyHTML,
  hwcheckProjectPanelHTML,
  hwcheckRecentEmptyHTML,
  hwcheckRecentHTML,
  hwcheckUnverifiedNoteHTML,
} from "/js/fx/hwcheck-project.js";
import {
  hwcheckCanPreview,
  hwcheckCodeTarget,
  hwcheckDroppedNoteHTML,
  hwcheckEmptyHTML,
  hwcheckErrorHTML,
  hwcheckGenerateErrorHTML,
  hwcheckPanelHTML,
  hwcheckPlatformCardsHTML,
  hwcheckPlatformLabel,
  hwcheckPlatformState,
} from "/js/fx/hwcheck-state.js";
import { hwcheckAdviceHTML, hwcheckCanTriage, hwcheckTriageErrorHTML } from "/js/fx/hwcheck-triage.js";
import {
  hwcheckBoardSharesHTML,
  hwcheckDeviceChipsHTML,
  hwcheckDeviceEmptyHTML,
  hwcheckDeviceGroupNoticeHTML,
  hwcheckDevicePool,
  hwcheckMissingDevicesHTML,
  hwcheckOrderHTML,
  hwcheckPinCapacityNoteHTML,
  hwcheckPinFixHTML,
  hwcheckPinGroupsHTML,
  hwcheckWiringTableHTML,
} from "/js/fx/hwcheck-wiring.js";
import { moduleGridCountText, moduleGridHTML } from "/js/fx/module.js";
import {
  myDeviceDraftPanelHTML,
  myDeviceFormHTML,
  myDeviceListHTML,
  myDeviceMaterialHTML,
} from "/js/fx/my-devices.js";
import { chosenPlatform } from "/js/ui/generate-recommend.js";
// 本栏目自己的状态（与生成流程零共享）：选中平台 + 两个输出通道开关 +
// 选中的器件 + 器件搜索词 + 输出父目录 + 板侧视图（接线 / 冲突 / 顺序）+
// 这一趟的检测计划（逐件专精小节 + 未专精点名，工单 04）+ 最近一次预览/生成
// 的结果 + 上板清单勾选态。
export const hwcheckUI = {
  platform: "",
  debug_uart: true,
  oled: true,
  devices: [],
  deviceQuery: "",
  parentDir: "",
  preview: "",
  outputHint: "",
  wiring: null,       // 板侧视图（服务端投影：接线行 / 同脚组 / 顺序 / 缺条目）
  exclusiveGroups: [], // 库级互斥组（服务端按平台投影，工单 05：单选交换的判据）
  sections: [],       // 逐件专精小节（服务端按库内配方解析，工单 04）
  unspecialized: [],  // 走通用降级的器件（未专精：只验总线和初始化，工单 07）
  custom: [],         // 自建件的检测计划（服务端投影：标注 / 接线 / 出不出小节，工单 05）
  console: null,      // 串口命令台载荷（配方命令 + 既有命令 + 能不能复测，工单 06）
  consoleNote: "",    // 复测字符余量提示（服务端给；空 = 不吭声，工单 hardening/05）
  dropped: [],        // 选中的自建件里**已经不在器件库**的那些（工单 ci-gate-fixes/09）
  project: null,      // 当前正在看的检测工程（生成或回读来的）
  checklistChecked: [],
  symptom: "",        // 学生填的"实际现象"（工单 08：AI 排障的输入）
  advice: null,       // 最近一次排障建议（服务端给；degraded = 兜底文案）
  adviceMessage: "",  // 模型失败原因（只在降级时非空；与建议正文分开显示）
  adviceDegraded: false,
  triageError: "",    // 排障**请求**失败（网络 / 400）——与"模型失败"不是一回事
  recent: [],
  generateError: "",
  previewError: "",   // 预览失败（工单 hardening/07）：专用文案，与"接线表取不到"分开
  busy: false,
  seeded: false,
  // —— 「我的器件」（库外件，工单 02）：件与平台无关，所以这些键不随平台清空 ——
  myDevices: [],        // 现有自建件（服务端真源；页面不自己记账）
  knownSlugs: [],       // 库内 slug 集（页面据此在提交前拦住撞名的 id）
  myForm: null,         // 正在编辑 / 新建的表单值（null = 表单收起）
  myEditId: "",         // 正在编辑的那一件的 id（新建 = 空串；校验"撞已有件"时要排除自己）
  myFormError: "",      // 表单校验理由（服务端 400 的中文原样带出）
  myError: "",          // 列表读不出来的理由（坏条目等）
  myBusy: false,
  myMaterial: "",       // 资料文本框里的字（工单 07：贴的文字 / 文件抽出的文本）
  myMaterialBusy: false, // 抽取进行中（按钮置灰）
  myMaterialMessage: "", // 资料入口的提示（本地提示或降级原因）
  myDraft: null,        // 最近一次草稿载荷（未确认前不落盘——它只是表单预填）
  myDraftApplied: false, // 草稿已填进表单（面板按钮换成核对提示）
};

export function hwcheckPlatforms() {
  return (state && state.platforms) || [];
}

// 模块库载荷（/api/modules 由启动区拉进全局 state，与模块库页 / 生成页同一份）
function hwcheckModules() {
  return (state && state.modules) || [];
}

function platformLabel(id) {
  return hwcheckPlatformLabel(hwcheckPlatforms(), id);
}

// 本地备忘（隐私模式 / 禁用存储时静默降级：勾选态存不下不该让栏目不可用）
export function readStored(key) {
  try { return localStorage.getItem(key) || ""; } catch { return ""; }
}

export function writeStored(key, value) {
  try { localStorage.setItem(key, value); } catch { /* 存不下就算了 */ }
}

// 编译能力（/api/state 的 toolchains）：状态还没到 = 不预先唱衰（真缺工具链时
// 后端 400 给准话）；明确 false = 编译按钮置灰 + 大声说明"未验证"。
function compileReady() {
  const platform = hwcheckUI.project && hwcheckUI.project.platform;
  if (!platform) return true;
  const toolchains = (state && state.toolchains) || {};
  return toolchains[platform] !== false;
}

export function renderHwcheckPlatforms() {
  if (!hwcheckUI.seeded) {
    // 首次进入（或全局状态刚到位）：继承全局当前平台 → 之后以栏目自己的选择为准
    hwcheckUI.platform = hwcheckPlatformState(
      hwcheckPlatforms(), chosenPlatform, hwcheckUI.platform).platform;
    hwcheckUI.seeded = true;
  } else if (!hwcheckUI.platform) {
    hwcheckUI.platform = hwcheckPlatformState(
      hwcheckPlatforms(), chosenPlatform, "").platform;
  }
  $("hwcheck-platforms").innerHTML = hwcheckPlatformCardsHTML(
    hwcheckPlatforms(), hwcheckUI.platform);
  const canGo = hwcheckCanPreview(hwcheckUI);
  const preview = $("btn-hwcheck-preview");
  // 进行中禁用（工单 hwcheck-hygiene/06）：与「生成」按钮同一条规矩——预览也是要等的
  // 动作（零工具链但要走一遍装配），按住时按钮必须是**看得见的**不可点状态，
  // 而不是"点了没反应"（函数内部那道 busy 早退是兜底，不是给人看的）。
  if (preview) preview.disabled = !canGo || hwcheckUI.busy;
  const generate = $("btn-hwcheck-generate");
  if (generate) generate.disabled = !canGo || hwcheckUI.busy;
}

// renderHwcheckChannelNote()：「这两路默认撞脚」的**生成前**引导（mspm0 双通道）——
// 文案与判据都在 fx（hwcheckChannelNoteHTML），本层只放进容器。
export function renderHwcheckChannelNote() {
  const box = $("hwcheck-channel-note");
  if (!box) return;
  box.innerHTML = hwcheckChannelNoteHTML(
    hwcheckUI.platform, hwcheckUI.debug_uart, hwcheckUI.oled);
}

// renderHwcheckUnverifiedNote()：栏目顶部的**总口径**（工单 hwcheck-hardening/02）——
// 「配方与探测小节尚未在真板上验证过」。文案在 fx，本层只放进容器；它不随选择变化，
// 所以只在初始化时渲染一次。
export function renderHwcheckUnverifiedNote() {
  const box = $("hwcheck-unverified-note");
  if (!box) return;
  box.innerHTML = hwcheckUnverifiedNoteHTML();
}

export function renderHwcheckOutput() {
  const box = $("hwcheck-output");
  // 预览失败（工单 hwcheck-hardening/07）：这里显示**说得对**的那句（"检测程序预览失败"），
  // 而不是把用户引去查接线表；同时上面已经把上一次的 main.c 清掉了——失败之后还留着
  // 上一组器件的程序，是最容易让人烧错东西的一种"静默过期产物"。
  const error = hwcheckUI.previewError
    ? hwcheckErrorHTML(hwcheckUI.previewError) : "";
  const shell = hwcheckPanelHTML(hwcheckUI.preview, hwcheckUI.outputHint);
  if (shell) {
    // 产物区壳由 fx/hwcheck-state.js 单源给出；main.c 文本走 textContent（天然不解释 HTML）
    box.innerHTML = error + shell;
    const code = hwcheckCodeTarget(box);
    if (code) code.textContent = hwcheckUI.preview;
    return;
  }
  box.innerHTML = error || hwcheckEmptyHTML(
    "选好平台后点「预览检测程序」——这里会显示这一趟要烧进板子的 main.c"
    + "（LED 心跳 + 输出通道自报，还没有选任何器件）。");
}

export function renderHwcheckProject() {
  const box = $("hwcheck-project");
  if (!box) return;
  const error = hwcheckUI.generateError
    ? hwcheckGenerateErrorHTML(hwcheckUI.generateError) : "";
  const panel = hwcheckUI.project
    ? hwcheckProjectPanelHTML(hwcheckUI.project, {
      platformLabel: platformLabel(hwcheckUI.project.platform),
      compileReady: compileReady(),
    })
    : hwcheckProjectEmptyHTML();
  if (error) box.innerHTML = error + panel;
  else if (panel) box.innerHTML = panel;
}

// 焦点恢复（工单 hwcheck-hygiene/06）：勾选类整块重绘后，把焦点送回"刚操作的那一项"。
//
// 为什么要它：这些区块都是 `innerHTML = …` 全量重绘，刚按下的复选框 / 刚点的那张卡
// 会被替换掉、焦点掉回 body——学生连续勾十几项时每次都要重新用鼠标找位置。
// 口径：**谁触发的重绘谁负责写 `pendingFocusSelector`**，渲染函数收尾统一 `applyPendingFocus()`；
// 找不到目标（比如那一项被移除了）就什么都不做（不抢焦点、不报错）。
let pendingFocusSelector = "";

export function selectorValue(value) {
  // 属性选择器里的值转义（slug / 清单 id 都是普通词，这里只兜住引号与反斜杠）
  return String(value == null ? "" : value).replace(/["\\]/g, "\\$&");
}

// setPendingFocus(selector)：整块重绘前**登记**焦点落点（工单 hwcheck-hygiene/11）。
// 为什么是一个函数而不是导出那个 `let`：ESM 的导入绑定只读，跨件赋值写不了；状态留在
// 本件，重绘收尾由 applyPendingFocus() 统一消费（口径见上面那段）。
// 消费方 = 入口 / 器件 / 动作三件（谁触发重绘谁登记）。
export function setPendingFocus(selector) {
  pendingFocusSelector = String(selector || "");
}

function applyPendingFocus() {
  const selector = pendingFocusSelector;
  pendingFocusSelector = "";
  if (!selector) return;
  const el = document.querySelector(selector);
  if (el && typeof el.focus === "function") el.focus();
}

export function renderHwcheckChecklist() {
  const box = $("hwcheck-checklist");
  if (!box) return;
  const items = (hwcheckUI.project && hwcheckUI.project.checklist) || [];
  if (!items.length) {
    // 空清单这条早退也要把待办焦点清掉（评审整改）：否则一个陈旧选择器会等到
    // **下一次无关重绘**才被消费，焦点莫名其妙跳到别处。
    pendingFocusSelector = "";
    box.innerHTML = '<div class="muted">生成检测工程后，这里会出现这次要逐项核对的清单'
      + '（应看到什么 / 不对先查哪里）。</div>';
    return;
  }
  box.innerHTML = hwcheckChecklistProgressHTML(items, hwcheckUI.checklistChecked)
    + hwcheckChecklistHTML(items, hwcheckUI.checklistChecked);
  applyPendingFocus();
}

export function renderHwcheckRecent() {
  const box = $("hwcheck-recent");
  if (!box) return;
  const html = hwcheckRecentHTML(
    hwcheckUI.recent, hwcheckUI.project ? hwcheckUI.project.outputDir : "");
  box.innerHTML = html || hwcheckRecentEmptyHTML();
}

// —— 器件挑选（工单 03）：chips（已选）+ 缺条目点名 + 卡片网格（可搜索） ——
// 三块都只渲染服务端载荷与 fx 纯件：chips 复用推荐区 chip 渲染、网格复用模块库
// 卡片渲染（moduleGridHTML），本层不判"哪个器件能测"。
export function renderHwcheckDevices() {
  const modules = hwcheckModules();
  const chips = $("hwcheck-device-chips");
  if (chips) {
    const html = hwcheckDeviceChipsHTML(
      hwcheckUI.devices, modules, hwcheckUI.platform);
    chips.innerHTML = html || hwcheckDeviceEmptyHTML();
  }
  const missing = $("hwcheck-device-missing");
  if (missing) {
    missing.innerHTML = hwcheckMissingDevicesHTML(
      hwcheckUI.wiring ? hwcheckUI.wiring.missing : []);
  }
  // 同组互斥提示（工单 05）：组清单来自服务端载荷（库内 exclusive_group 单源），
  // 本层只渲染——"这一组只能选一件"与"再点谁会自动换掉谁"都由 fx 纯件说清。
  const groups = $("hwcheck-device-groups");
  if (groups) {
    groups.innerHTML = hwcheckDeviceGroupNoticeHTML(
      hwcheckUI.exclusiveGroups, hwcheckUI.devices);
  }
  const grid = $("hwcheck-device-grid");
  if (grid) {
    const pool = hwcheckDevicePool(modules);
    grid.innerHTML = moduleGridHTML(
      pool, hwcheckUI.devices, hwcheckUI.deviceQuery, hwcheckUI.platform);
    const count = $("hwcheck-device-count");
    if (count) {
      count.textContent = moduleGridCountText(
        pool, hwcheckUI.devices, hwcheckUI.deviceQuery);
    }
  }
  // 「我的器件」的行也随选择集重绘：它那行的加选按钮是**两态**的（加进 / 已在），
  // 而它跟 chips 是两个容器——只重绘 chips 的话，从 chip 那侧取消加选后，
  // 行上还写着「✓ 已在这次检测里」（界面自相矛盾）。这里刻意只换列表那一块：
  // 表单必须原样留着（整块重绘会把正在填的字刷掉——见 syncMyDeviceForm 的说明）。
  const myList = $("my-devices-list");
  if (myList) myList.innerHTML = myDeviceListHTML(hwcheckUI.myDevices, hwcheckUI.devices);
  applyPendingFocus();
  renderHwcheckHandoff();
}

// —— 带入生成页（工单 hwcheck-acceptance/04）：判据全在 fx，本层只喂数据 ——
//
// 库内词表取自 /api/modules 载荷（生成页模块池与检测页器件网格吃的是同一份）——
// **刻意不用** hwcheckUI.knownSlugs：那份来自 /api/my-devices，读不到时是空集，
// 会把所有器件都判成"词表外"（一次读盘失败就变成"谁都带不过去"）。
// 反过来，"是不是库外件"只认 /api/my-devices 那份清单（判据不写成 id 前缀）。
export function hwcheckHandoff() {
  return hwcheckHandoffPlan(
    hwcheckUI.devices,
    hwcheckModules().map((m) => m && m.slug),
    hwcheckUI.myDevices,
  );
}

export function renderHwcheckHandoff() {
  const box = $("hwcheck-handoff");
  if (!box) return;
  box.innerHTML = hwcheckHandoffHTML(hwcheckHandoff(), {
    pinFixes: ((hwcheckUI.wiring || {}).pin_fixes || []).length,
    platforms: hwcheckPlatforms(),
    from: hwcheckUI.platform,
    to: chosenPlatform || "",
  });
}

// —— 「我的器件」（库外件，工单 02）：列表 + 表单 ——
// 三块都只渲染服务端载荷与 fx 纯件：判据（id 文法等）在服务端，表单那个校验只是
// "别让用户白跑一趟"（同一个函数也用来给保存按钮置灰的理由）。
export function renderMyDevices() {
  const listBox = $("my-devices-list");
  if (listBox) {
    listBox.innerHTML = hwcheckUI.myError
      ? `<div class="error">「我的器件」读不出来：${hwcheckUI.myError}</div>`
      : myDeviceListHTML(hwcheckUI.myDevices, hwcheckUI.devices);
  }
  const formBox = $("my-devices-form");
  if (formBox) {
    formBox.innerHTML = hwcheckUI.myForm
      ? myDeviceFormHTML(hwcheckUI.myForm, hwcheckUI.myFormError) : "";
  }
  // 资料入口与草稿面板（工单 07）：只在显式动作后整块重绘——文本框打字只同步
  // state（见下面的 input 委托），不打断输入。
  const materialBox = $("my-devices-material");
  if (materialBox) {
    materialBox.innerHTML = myDeviceMaterialHTML({
      text: hwcheckUI.myMaterial,
      busy: hwcheckUI.myMaterialBusy,
      message: hwcheckUI.myMaterialMessage,
    });
  }
  const draftBox = $("my-devices-draft");
  if (draftBox) {
    draftBox.innerHTML = hwcheckUI.myDraft
      ? myDeviceDraftPanelHTML(hwcheckUI.myDraft, hwcheckUI.myDraftApplied) : "";
  }
  const open = $("btn-my-device-new");
  if (open) open.disabled = !!hwcheckUI.myBusy;
  applyPendingFocus();
}

// —— 接线表 / 默认脚冲突 / 建议顺序（工单 03）：三块全部来自服务端板侧视图 ——
// 前端一个字都不判：撞不撞脚、能不能共享、谁先测，都是既有判据算出来的。
export function renderHwcheckWiring() {
  const wiringBox = $("hwcheck-wiring");
  const conflictBox = $("hwcheck-conflicts");
  const orderBox = $("hwcheck-order");
  // 预览整份失败时（previewError）：这里**什么都不说**——错误已经在产物区用专用文案说清了，
  // 再摆一句"选好平台后点预览"等于让刚点过的学生以为自己没点。
  // 注意没有"接线表单独取不到"这一档了（工单 hwcheck-hardening/07）：接线表与主程序**同一次
  // 请求**回来，那档文案（hwcheckWiringErrorHTML）依据的前提本来就不成立，已删。
  const empty = hwcheckUI.previewError
    ? ""
    : (hwcheckUI.wiring
      ? hwcheckPinFixHTML(hwcheckUI.wiring.pin_fixes)
        // 「这一趟没判装不装得下」紧随其后（工单 hwcheck-hygiene/04）：母版没导入时
        // 容量判定跳过，页面必须说出来——不然看起来像"检查过了、没问题"。
        + hwcheckPinCapacityNoteHTML(hwcheckUI.wiring.capacity_note)
        + hwcheckWiringTableHTML(hwcheckUI.wiring.rows, hwcheckUI.wiring.footnote)
        // 自建件那一行接在表**下面**（"你的器件 … 接到上面接线表里 i2c_probe 的
        // 那对脚"——那句话指的就是刚读完的这张表）。空 = 空串（既有页面不变）。
        + hwcheckCustomWiringHTML(hwcheckUI.custom)
      : '<div class="muted">选好平台后点「预览检测程序」（或选一件器件），'
        + "这里会出现这一趟要接的线与默认脚冲突。</div>");
  if (wiringBox) wiringBox.innerHTML = empty;
  if (conflictBox) {
    conflictBox.innerHTML = hwcheckUI.wiring
      ? hwcheckPinGroupsHTML(hwcheckUI.wiring.groups, hwcheckUI.wiring.rows)
        + hwcheckBoardSharesHTML(
          hwcheckUI.wiring.board_shares, hwcheckUI.wiring.rows)
      : "";
  }
  if (orderBox) {
    orderBox.innerHTML = hwcheckUI.wiring
      ? hwcheckOrderHTML(
        hwcheckUI.wiring.order, hwcheckUI.wiring.guide, hwcheckUI.wiring.reason)
      : "";
  }
}

// —— 逐件专精小节 / 未专精点名（工单 04）：两块都只渲染服务端载荷 ——
// 判据（这件的配方在不在、引用的接口真不真）全在服务端；前端一个字都不判。
export function renderHwcheckSections() {
  const box = $("hwcheck-sections");
  if (!box) return;
  // 一件专精件都没有时说清"为什么这条是空的"（不是错误状态，但也不留空白）
  const panel = hwcheckSectionsHTML(hwcheckUI.sections);
  box.innerHTML = (panel || hwcheckSectionsEmptyHTML())
    + hwcheckUnspecializedHTML(hwcheckUI.unspecialized);
}

// —— 自建件的检测计划（工单 hwcheck-unknown-device/05）：只渲染服务端载荷 ——
// 标注词 / 接线那一行 / "这一趟对它做什么" / 出不出小节的判据全部在服务端
// （`hwcheck_custom` 单源）；前端一个字都不判，也**不自己判总线**——那会让页面与
// 产物两处各说各话。一件自建件都没有时写空串（既有页面逐字不变）。
export function renderHwcheckCustom() {
  const box = $("hwcheck-custom");
  if (!box) return;
  box.innerHTML = hwcheckCustomPlanHTML(hwcheckUI.custom);
}

// applyDroppedDevices(payload)：这一趟服务端**摘掉了哪几件"已经不在器件库里"的自建件**
// （工单 ci-gate-fixes/09）——两件事一起做：
// ① 如实记下（说明条由 renderHwcheckDropped 渲染，文案在 fx）；
// ② **把本地选择集对齐**：摘掉的件不再算"已选"（置灰回「加进这次检测」）——不然界面
//    显示已选、这一趟却没带它，两边不一致，用户会以为"选了没用"。
// 只认服务端载荷：前端不自己拿"我的器件"清单去猜哪件还在（那是第二份判据）。
export function applyDroppedDevices(payload) {
  const dropped = (payload && Array.isArray(payload.dropped_devices))
    ? payload.dropped_devices.map(String) : [];
  hwcheckUI.dropped = dropped;
  if (dropped.length) {
    const away = new Set(dropped);
    hwcheckUI.devices = (hwcheckUI.devices || []).filter((slug) => !away.has(slug));
  }
}

// renderHwcheckDropped()：说明条（判据与文案在 fx，本层只放进容器）。
function renderHwcheckDropped() {
  const box = $("hwcheck-dropped");
  if (box) box.innerHTML = hwcheckDroppedNoteHTML(hwcheckUI.dropped);
}

// —— 串口命令台（工单 module-hwcheck/06）：只渲染服务端载荷（命令表 = 库内配方
// + 自建件那几件）——
// 前端不判"哪个字符是谁的"：判重与保留字都在服务端（两件抢字符 = 构建期 400），
// 自建件的字符也是服务端分配的（工单 hwcheck-unknown-device/06）。
export function renderHwcheckConsole() {
  const box = $("hwcheck-console");
  if (!box) return;
  // 预览整份失败时：命令台也不摆那句"选好器件后点预览"（错误已在产物区说清，见 07 单）。
  box.innerHTML = hwcheckUI.previewError ? "" : (hwcheckConsoleHTML(hwcheckUI.console)
    || '<div class="muted">选好器件后点「预览检测程序」：这里会列出这一趟的串口'
      + "复测命令（库内器件按配方、自建件按它自己的探测小节），"
      + "以及没有串口时为什么不能交互复测。</div>");
  // 复测字符余量的事前提示（工单 hwcheck-hardening/05）：文案由服务端给（空 = 不吭声），
  // 前端不自己算"还剩几个字符"——那等于把分配判据抄一份到浏览器里。
  const note = $("hwcheck-console-note");
  if (note) note.innerHTML = hwcheckConsoleNoteHTML(hwcheckUI.consoleNote);
}

// renderHwcheckAdvice()：现象回填 + AI 排障面板（工单 08）。
// 三种内容分开放：**请求失败**（triageError，红字）/ **模型失败**（兜底建议 +
// message 一句）/ **模型结论**（建议正文）——把"模型没答上来"说成"检测失败"
// 会把学生引到错的地方去查。
export function renderHwcheckAdvice() {
  const box = $("hwcheck-advice");
  const button = $("btn-hwcheck-triage");
  if (button) {
    button.disabled = !hwcheckCanTriage(hwcheckUI) || hwcheckUI.busy;
    button.textContent = hwcheckUI.busy ? "分析中…" : "让 AI 分析";
  }
  const status = $("hwcheck-triage-status");
  if (status) {
    status.textContent = hwcheckUI.adviceMessage
      ? "AI 这次没给出来：" + hwcheckUI.adviceMessage
      : "";
  }
  if (!box) return;
  box.innerHTML = (hwcheckUI.triageError
    ? hwcheckTriageErrorHTML(hwcheckUI.triageError) : "")
    + hwcheckAdviceHTML(hwcheckUI.advice);
}

export function renderHwcheckPanel() {
  renderHwcheckPlatforms();
  renderHwcheckChannelNote();
  renderMyDevices();
  renderHwcheckDropped();
  renderHwcheckOutput();
  renderHwcheckDevices();
  renderHwcheckWiring();
  renderHwcheckSections();
  renderHwcheckCustom();
  renderHwcheckConsole();
  renderHwcheckProject();
  renderHwcheckChecklist();
  renderHwcheckAdvice();
  renderHwcheckRecent();
}

