// ui/hwcheck.js — 硬件检测栏目的 DOM 胶水（工单 module-hwcheck/01 + 02）。
//
// 单向依赖：ui → fx / app（纯件在 fx/hwcheck.js，本文件只读状态、写 DOM、
// 发请求）。栏目独立于赛题工作流：不读题面、不读已选模块、不写最近工程记录。
//
// 工单 02 起这个栏目从"预览文本"走到"真的上板"：
//   生成 POST /api/hwcheck/generate（复用生成内核，新子目录不覆盖）
//   → 编译复用既有执行体 ui/fix-center-core.runCompileOnceCore（不写第四个
//     SSE 编译消费器）+ 既有判读纯件 fx/code-compile
//   → 烧录复用既有共享执行体 ui/flash.js flashRunShared（400 出中文指引卡）
//   → 上板清单勾选态存 localStorage（按检测工程目录分），刷新回显走
//     GET /api/hwcheck/project 的服务端真源。
import { $, apiGet, apiPost, state, toast, toastError } from "/js/app.js";
import { chosenPlatform } from "/js/ui/generate-recommend.js";
import { bindModuleInfoEntry, openModuleInfo } from "/js/ui/generate-recommend.js";
import { flashRunShared } from "/js/ui/flash.js";
import { runCompileOnceCore } from "/js/ui/fix-center-core.js";
import {
  compileStatusText, compileStatusClass, compileErrorRowsHTML,
} from "/js/fx/code-compile.js";
import {
  moduleGridHTML, moduleGridCountText,
} from "/js/fx/module.js";
import {
  hwcheckPlatformState, hwcheckSelectPlatform, hwcheckPickState,
  hwcheckRequestPayload, hwcheckCanPreview, hwcheckPlatformCardsHTML,
  hwcheckGenerateErrorHTML, hwcheckEmptyHTML, hwcheckPanelHTML,
  hwcheckCodeTarget, hwcheckPreviewState, hwcheckPlatformLabel,
  hwcheckGeneratePayload, hwcheckChecklistKey, hwcheckCheckedIds,
  hwcheckChecklistToggle, hwcheckChecklistHTML, hwcheckChecklistProgressHTML,
  hwcheckProjectState, hwcheckProjectPanelHTML, hwcheckProjectEmptyHTML,
  hwcheckRecentHTML, hwcheckRecentEmptyHTML, hwcheckChannelNoteHTML,
  hwcheckDevicePick, hwcheckDevicePool, hwcheckDeviceChipsHTML,
  hwcheckDeviceEmptyHTML, hwcheckMissingDevicesHTML, hwcheckWiringTableHTML,
  hwcheckDeviceGroupNoticeHTML,
  hwcheckPinGroupsHTML, hwcheckBoardSharesHTML, hwcheckOrderHTML,
  hwcheckBoardState, hwcheckWiringErrorHTML,
  hwcheckSectionsState, hwcheckSectionsHTML, hwcheckUnspecializedHTML,
  hwcheckSectionsEmptyHTML,
  hwcheckConsoleState, hwcheckConsoleHTML,
  hwcheckCanTriage, hwcheckTriagePayload, hwcheckChecklistPayload,
  hwcheckAdviceState, hwcheckRecordState, hwcheckTriageErrorHTML,
  hwcheckAdviceHTML, hwcheckChecklistState,
  HWCHECK_PARENT_KEY, HWCHECK_LAST_DIR_KEY,
} from "/js/fx/hwcheck.js";

// 本栏目自己的状态（与生成流程零共享）：选中平台 + 两个输出通道开关 +
// 选中的器件 + 器件搜索词 + 输出父目录 + 板侧视图（接线 / 冲突 / 顺序）+
// 这一趟的检测计划（逐件专精小节 + 未专精点名，工单 04）+ 最近一次预览/生成
// 的结果 + 上板清单勾选态。
const hwcheckUI = {
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
  console: null,      // 串口命令台载荷（配方命令 + 既有命令 + 能不能复测，工单 06）
  project: null,      // 当前正在看的检测工程（生成或回读来的）
  checklistChecked: [],
  symptom: "",        // 学生填的"实际现象"（工单 08：AI 排障的输入）
  advice: null,       // 最近一次排障建议（服务端给；degraded = 兜底文案）
  adviceMessage: "",  // 模型失败原因（只在降级时非空；与建议正文分开显示）
  adviceDegraded: false,
  triageError: "",    // 排障**请求**失败（网络 / 400）——与"模型失败"不是一回事
  recent: [],
  generateError: "",
  wiringError: "",
  busy: false,
  seeded: false,
};

function hwcheckPlatforms() {
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
function readStored(key) {
  try { return localStorage.getItem(key) || ""; } catch { return ""; }
}

function writeStored(key, value) {
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

function renderHwcheckPlatforms() {
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
  if (preview) preview.disabled = !canGo;
  const generate = $("btn-hwcheck-generate");
  if (generate) generate.disabled = !canGo || hwcheckUI.busy;
}

// renderHwcheckChannelNote()：「这两路默认撞脚」的**生成前**引导（mspm0 双通道）——
// 文案与判据都在 fx（hwcheckChannelNoteHTML），本层只放进容器。
function renderHwcheckChannelNote() {
  const box = $("hwcheck-channel-note");
  if (!box) return;
  box.innerHTML = hwcheckChannelNoteHTML(
    hwcheckUI.platform, hwcheckUI.debug_uart, hwcheckUI.oled);
}

function renderHwcheckOutput() {
  const box = $("hwcheck-output");
  const shell = hwcheckPanelHTML(hwcheckUI.preview, hwcheckUI.outputHint);
  if (shell) {
    // 产物区壳由 fx/hwcheck.js 单源给出；main.c 文本走 textContent（天然不解释 HTML）
    box.innerHTML = shell;
    const code = hwcheckCodeTarget(box);
    if (code) code.textContent = hwcheckUI.preview;
    return;
  }
  box.innerHTML = hwcheckEmptyHTML(
    "选好平台后点「预览检测程序」——这里会显示这一趟要烧进板子的 main.c"
    + "（LED 心跳 + 输出通道自报，还没有选任何器件）。");
}

function renderHwcheckProject() {
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

function renderHwcheckChecklist() {
  const box = $("hwcheck-checklist");
  if (!box) return;
  const items = (hwcheckUI.project && hwcheckUI.project.checklist) || [];
  if (!items.length) {
    box.innerHTML = '<div class="muted">生成检测工程后，这里会出现这次要逐项核对的清单'
      + '（应看到什么 / 不对先查哪里）。</div>';
    return;
  }
  box.innerHTML = hwcheckChecklistProgressHTML(items, hwcheckUI.checklistChecked)
    + hwcheckChecklistHTML(items, hwcheckUI.checklistChecked);
}

function renderHwcheckRecent() {
  const box = $("hwcheck-recent");
  if (!box) return;
  const html = hwcheckRecentHTML(
    hwcheckUI.recent, hwcheckUI.project ? hwcheckUI.project.outputDir : "");
  box.innerHTML = html || hwcheckRecentEmptyHTML();
}

// —— 器件挑选（工单 03）：chips（已选）+ 缺条目点名 + 卡片网格（可搜索） ——
// 三块都只渲染服务端载荷与 fx 纯件：chips 复用推荐区 chip 渲染、网格复用模块库
// 卡片渲染（moduleGridHTML），本层不判"哪个器件能测"。
function renderHwcheckDevices() {
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
}

// —— 接线表 / 默认脚冲突 / 建议顺序（工单 03）：三块全部来自服务端板侧视图 ——
// 前端一个字都不判：撞不撞脚、能不能共享、谁先测，都是既有判据算出来的。
function renderHwcheckWiring() {
  const wiringBox = $("hwcheck-wiring");
  const conflictBox = $("hwcheck-conflicts");
  const orderBox = $("hwcheck-order");
  const error = hwcheckUI.wiringError;
  if (wiringBox) {
    wiringBox.innerHTML = error
      ? hwcheckWiringErrorHTML(error)
      : (hwcheckUI.wiring
        ? hwcheckWiringTableHTML(hwcheckUI.wiring.rows, hwcheckUI.wiring.footnote)
        : '<div class="muted">选好平台后点「预览检测程序」（或选一件器件），'
          + "这里会出现这一趟要接的线与默认脚冲突。</div>");
  }
  if (conflictBox) {
    conflictBox.innerHTML = (error || !hwcheckUI.wiring)
      ? "" : hwcheckPinGroupsHTML(hwcheckUI.wiring.groups, hwcheckUI.wiring.rows)
        + hwcheckBoardSharesHTML(
          hwcheckUI.wiring.board_shares, hwcheckUI.wiring.rows);
  }
  if (orderBox) {
    orderBox.innerHTML = (error || !hwcheckUI.wiring)
      ? "" : hwcheckOrderHTML(
        hwcheckUI.wiring.order, hwcheckUI.wiring.guide, hwcheckUI.wiring.reason);
  }
}

// —— 逐件专精小节 / 未专精点名（工单 04）：两块都只渲染服务端载荷 ——
// 判据（这件的配方在不在、引用的接口真不真）全在服务端；前端一个字都不判。
function renderHwcheckSections() {
  const box = $("hwcheck-sections");
  if (!box) return;
  // 一件专精件都没有时说清"为什么这条是空的"（不是错误状态，但也不留空白）
  const panel = hwcheckSectionsHTML(hwcheckUI.sections);
  box.innerHTML = (panel || hwcheckSectionsEmptyHTML())
    + hwcheckUnspecializedHTML(hwcheckUI.unspecialized);
}

// —— 串口命令台（工单 06）：只渲染服务端载荷（命令表 = 库内配方）——
// 前端不判"哪个字符是谁的"：判重与保留字都在服务端（两件抢字符 = 构建期 400）。
function renderHwcheckConsole() {
  const box = $("hwcheck-console");
  if (!box) return;
  box.innerHTML = hwcheckConsoleHTML(hwcheckUI.console)
    || '<div class="muted">选好器件后点「预览检测程序」：这里会列出这一趟的串口'
      + "复测命令（哪些能复测由库内配方决定），以及没有串口时为什么不能交互复测。</div>";
}

// renderHwcheckAdvice()：现象回填 + AI 排障面板（工单 08）。
// 三种内容分开放：**请求失败**（triageError，红字）/ **模型失败**（兜底建议 +
// message 一句）/ **模型结论**（建议正文）——把"模型没答上来"说成"检测失败"
// 会把学生引到错的地方去查。
function renderHwcheckAdvice() {
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
  renderHwcheckOutput();
  renderHwcheckDevices();
  renderHwcheckWiring();
  renderHwcheckSections();
  renderHwcheckConsole();
  renderHwcheckProject();
  renderHwcheckChecklist();
  renderHwcheckAdvice();
  renderHwcheckRecent();
}

// adoptProject(payload, dir, opts)：把一次生成 / 回读的结果放到页面上——同时记住
// "上次看的是哪个目录"，并按该目录取出本地勾选态。
//
// `keepSelection=true`：**只带工程本体**（main.c / 清单 / 通道 / 预览），不覆盖
// 用户当前的器件与板侧视图。什么时候用：**自动回读**（页面加载时按上次目录回显）
// 撞上用户已经动过选择——他那一下才是最新意图，用旧工程里的器件集覆盖就是静默
// 抹掉他刚点的东西（照 refreshHwcheckView 的同一条并发纪律"过期响应绝不写状态"）。
function adoptProject(payload, dir, { keepSelection = false } = {}) {
  const adopted = hwcheckProjectState(hwcheckUI, payload);
  if (keepSelection) {
    Object.assign(hwcheckUI, hwcheckPreviewState(hwcheckUI, payload));
    hwcheckUI.project = adopted.project;
  } else {
    Object.assign(hwcheckUI, adopted);
    Object.assign(hwcheckUI, hwcheckPreviewState(hwcheckUI, payload));
  }
  const recordState = hwcheckRecordState(hwcheckUI, payload);
  Object.assign(hwcheckUI, recordState);
  // 勾选态：**服务端记录优先**（工单 08 起勾选也落盘）。判据是"这次回读**带没带
  // 记录**"（record 键在不在），不是"记录里的勾选空不空"——服务端把勾选全清空
  // 也是一种有效状态，拿空当"没有记录"会让本地备忘里的旧勾选复活（评审整改）。
  const hasRecord = !!(payload && payload.record);
  if (!hasRecord) {
    hwcheckUI.checklistChecked = hwcheckCheckedIds(
      readStored(hwcheckChecklistKey(dir)));
  }
  const symptomBox = $("hwcheck-symptom");
  if (symptomBox) symptomBox.value = hwcheckUI.symptom || "";
  hwcheckUI.triageError = "";
  hwcheckUI.generateError = "";
  hwcheckUI.wiringError = "";
  writeStored(HWCHECK_LAST_DIR_KEY, dir);
}

// refreshHwcheckView()：按**当前选择**重取一次板侧视图（接线 / 冲突 / 顺序）+
// 检测程序文本。选平台、勾通道、增删器件都走这一条路——判据在服务端，前端
// 不做增量更新（增量更新等于把判据抄一份到浏览器里）。
//
// 并发纪律（照 CONTEXT.md「展开收口」那条先例）：**过期响应绝不写状态，在途触发
// 一律排队**。连点两件器件会连发两次请求，而响应里带着 devices 回显——慢的那个
// 回来就把刚选的那件抹掉了。三条：
//   ① 在途时的触发记 pending，收尾用**当前**选择集重跑一次（不静默丢弃）；
//   ② 落地前比请求体快照，选择集变了 = 这次结果属于旧选择，不写状态；
//   ③ 失败只清板侧视图，**不清 main.c**——检测程序只依赖平台与通道（选器件不到
//      一分钟前刚渲染过的那份仍然有效），别让接线表取不到连坐预览（工单 03 评审）。
let hwcheckViewBusy = false;
let hwcheckViewPending = false;

function hwcheckSelectionKey() {
  return JSON.stringify(hwcheckRequestPayload(hwcheckUI));
}

async function refreshHwcheckView() {
  if (!hwcheckCanPreview(hwcheckUI)) return;
  if (hwcheckViewBusy) {
    hwcheckViewPending = true;
    return;
  }
  hwcheckViewBusy = true;
  const requestKey = hwcheckSelectionKey();
  try {
    const payload = await apiPost("/api/hwcheck/preview", hwcheckRequestPayload(hwcheckUI));
    if (hwcheckSelectionKey() !== requestKey) {
      // 选择集在途中又变了：这次结果属于旧选择，丢掉（排队的那次会补上）
    } else {
      Object.assign(hwcheckUI, hwcheckPreviewState(hwcheckUI, payload));
      Object.assign(hwcheckUI, hwcheckBoardState(hwcheckUI, payload));
      Object.assign(hwcheckUI, hwcheckSectionsState(hwcheckUI, payload));
      Object.assign(hwcheckUI, hwcheckConsoleState(hwcheckUI, payload));
      hwcheckUI.wiringError = "";
    }
  } catch (e) {
    if (hwcheckSelectionKey() === requestKey) {
      hwcheckUI.wiring = null;
      hwcheckUI.sections = [];
      hwcheckUI.unspecialized = [];
      hwcheckUI.console = null;
      hwcheckUI.wiringError = e && e.message ? e.message : String(e);
    }
  } finally {
    hwcheckViewBusy = false;
    if (hwcheckViewPending) {
      hwcheckViewPending = false;
      await refreshHwcheckView();
      return;   // 排队那次已经渲染过，别再渲染一遍
    }
  }
  renderHwcheckOutput();
  renderHwcheckDevices();
  renderHwcheckWiring();
  renderHwcheckSections();
  renderHwcheckConsole();   // 命令表也随载荷更新（真机验收抓到的漏渲染）
}

async function previewHwcheck() {
  if (!hwcheckCanPreview(hwcheckUI)) return;
  const box = $("hwcheck-output");
  if (box) box.innerHTML = '<div class="muted">正在渲染检测程序…</div>';
  await refreshHwcheckView();
}

// addHwcheckDevice(slug, on)：加 / 去一件器件 → 重绘挑选面 + 重取板侧视图。
// 选器件本身就是"我想看它怎么接"——所以这里顺手刷新一次（本地请求，零 LLM）。
// 组清单一起带上：同组互斥 = 单选交换（工单 05），判据来自服务端载荷的
// exclusive_groups（还没拿到时为空数组 = 老行为"只加不换"，提示会兜底说明）。
function addHwcheckDevice(slug, on = true) {
  Object.assign(hwcheckUI, hwcheckDevicePick(
    hwcheckUI, slug, on, hwcheckUI.exclusiveGroups));
  renderHwcheckDevices();
  refreshHwcheckView();
}

// generateHwcheck()：生成检测工程（后端确定性渲染 + 既有生成内核）。
// 成功 = 新子目录 + 一块工程面板 + 一份上板清单；失败 = 中文理由原样带出
// （含 mspm0 默认撞脚这类"引擎如实拒绝"）。
async function generateHwcheck() {
  if (!hwcheckCanPreview(hwcheckUI) || hwcheckUI.busy) return;
  hwcheckUI.busy = true;
  hwcheckUI.generateError = "";
  const box = $("hwcheck-project");
  if (box) box.innerHTML = '<div class="muted">正在生成检测工程（复制母版 + 写入检测程序）…</div>';
  renderHwcheckPlatforms();   // 生成期间两个按钮都置灰（防连点攒目录）
  try {
    const payload = await apiPost("/api/hwcheck/generate", hwcheckGeneratePayload(hwcheckUI));
    const dir = String(payload.output_dir || "");
    // 新工程 = 新的一次检测：现象与上一次的建议都归零（旧建议属于另一个工程，
    // 留着会让人以为"这个工程已经分析过了"）
    hwcheckUI.symptom = "";
    hwcheckUI.advice = null;
    hwcheckUI.adviceMessage = "";
    hwcheckUI.adviceDegraded = false;
    hwcheckUI.triageError = "";
    adoptProject(payload, dir);
    writeStored(HWCHECK_PARENT_KEY, hwcheckUI.parentDir);
    toast("ok", "检测工程已生成：" + dir);
    renderHwcheckPanel();
    loadHwcheckRecent();
  } catch (e) {
    hwcheckUI.generateError = e && e.message ? e.message : String(e);
    renderHwcheckProject();
  } finally {
    hwcheckUI.busy = false;
    renderHwcheckPlatforms();
  }
}

// restoreHwcheckProject(dir)：回读一次已有检测（刷新回显 / 点最近一次）。
//
// ⚠ **回读在途时用户动过选择就不覆盖他的器件**（工单 06 会话实测的静默抹除）：
// 页面加载的自动回读是异步的，而用户可能已经点了平台 / 加了器件——旧工程里的
// 器件集（常见是空的）一到就把刚选的那件抹掉，页面上看着像"点了没反应"。
// 判据用与 refreshHwcheckView 同一个选择集快照。
async function restoreHwcheckProject(dir) {
  if (!dir) return;
  const requestKey = hwcheckSelectionKey();
  try {
    const payload = await apiGet(
      "/api/hwcheck/project?output_dir=" + encodeURIComponent(dir));
    adoptProject(payload, dir, {
      keepSelection: hwcheckSelectionKey() !== requestKey,
    });
    renderHwcheckPanel();
  } catch (e) {
    // 上次那个工程被删了 / 不是检测工程：清掉备忘，不留下一个永远报错的入口
    writeStored(HWCHECK_LAST_DIR_KEY, "");
    hwcheckUI.project = null;
    hwcheckUI.generateError = "";
    renderHwcheckPanel();
    toastError(e, "上次的检测工程读不出来了");
  }
}

async function loadHwcheckRecent() {
  try {
    const payload = await apiGet(
      "/api/hwcheck/recent?parent_dir=" + encodeURIComponent(hwcheckUI.parentDir || ""));
    hwcheckUI.recent = (payload && payload.items) || [];
  } catch {
    hwcheckUI.recent = [];   // 最近列表读不到不影响检测本身
  }
  renderHwcheckRecent();
}

// —— 现象回填 + AI 排障（工单 08）：本栏目唯一的 LLM 入口 ——
//
// 两条独立的失败通道，分开显示（票面：LLM 失败不阻断 + 可重试）：
//   * 请求失败（网络 / 400：目录不在、记录文件坏）→ triageError 红字；
//   * 模型失败（服务端 200 + degraded）→ 兜底建议 + 一句失败原因（message），
//     现象与勾选**已经落盘**，学生改完现象再点一次就是重试。
async function submitHwcheckTriage() {
  if (!hwcheckCanTriage(hwcheckUI) || hwcheckUI.busy) return;
  // 现象的真源是**输入框**（不是 state 里那份可能过期的回显）：提交前先取一次
  const symptomBox = $("hwcheck-symptom");
  if (symptomBox) hwcheckUI.symptom = symptomBox.value;
  hwcheckUI.busy = true;
  hwcheckUI.triageError = "";
  renderHwcheckAdvice();
  try {
    const payload = await apiPost("/api/hwcheck/triage", hwcheckTriagePayload(hwcheckUI));
    Object.assign(hwcheckUI, hwcheckAdviceState(hwcheckUI, payload));
  } catch (e) {
    hwcheckUI.triageError = e && e.message ? e.message : String(e);
  } finally {
    hwcheckUI.busy = false;
  }
  renderHwcheckAdvice();
}

// syncHwcheckChecklist()：勾选落盘（零 LLM 轻端点）。本地备忘照旧写一份
// （离线 / 服务端读不到时的兜底）；服务端那份是"刷新 / 换机器也回显"的真源。
// 失败了只提示一句，不回滚勾选——学生刚点的那一下是有效输入。
async function syncHwcheckChecklist() {
  if (!hwcheckUI.project || !hwcheckUI.project.outputDir) return;
  try {
    const payload = await apiPost(
      "/api/hwcheck/checklist", hwcheckChecklistPayload(hwcheckUI));
    // 只认勾选（hwcheckChecklistState 的说明：整份采纳会吃掉还没提交的现象）
    Object.assign(hwcheckUI, hwcheckChecklistState(hwcheckUI, payload));
  } catch (e) {
    toastError(e, "清单勾选没能存进工程目录");
  }
}

// —— 编译 / 烧录 / 打开工程：三个动作都复用既有能力，本模块只接 DOM ——

function setCompileStatus(text, cls) {
  const el = $("hwcheck-compile-status");
  if (!el) return;
  el.textContent = text || "";
  el.className = "code-compile-status" + (cls ? " " + cls : "");
}

function setCompileErrors(html) {
  const el = $("hwcheck-compile-errors");
  if (el) el.innerHTML = html || "";
}

// runHwcheckCompile(dir, btn)：按钮由调用方（事件委托）传进来——**不要**用
// `querySelector('[data-hwcheck-compile="' + dir + '"]')` 反查：Windows 路径里的
// `\U` / `\u` 在 JS 字符串字面量里是非法/转义序列（会静默变成 `U`），选择器
// 永远匹配不上，表现为"按钮点了没反应"。
async function runHwcheckCompile(dir, btn) {
  if (!dir || hwcheckUI.busy) return;
  hwcheckUI.busy = true;
  if (btn) { btn.disabled = true; btn.textContent = "编译中…"; }
  setCompileErrors("");
  try {
    const done = await runCompileOnceCore({
      platform: hwcheckUI.project ? hwcheckUI.project.platform : "",
      outputDir: dir,
      callbacks: {
        onBanner: (stateName, text) => setCompileStatus(
          text, stateName === "success" ? "ok" : stateName === "fail" ? "err" : ""),
        onCompiled: (payload) => setCompileErrors(
          compileErrorRowsHTML((payload && payload.parsed_errors) || [])),
      },
    });
    setCompileStatus(compileStatusText(done), compileStatusClass(done));
  } catch (e) {
    // 工具链缺失 / 工程结构异常：后端 400 的中文理由原样带出（编译不调 LLM）
    setCompileStatus(e && e.message ? e.message : String(e), "err");
  } finally {
    hwcheckUI.busy = false;
    if (btn) { btn.disabled = false; btn.textContent = "编译验证"; }
  }
}

async function runHwcheckFlash(dir, btn) {
  if (!dir || hwcheckUI.busy) return;
  hwcheckUI.busy = true;
  if (btn) { btn.disabled = true; btn.textContent = "烧录中…"; }
  try {
    // 共享执行体：busy 文案 / 结果行 / 400 指引卡（工具缺失的中文安装指引）都在里面。
    // 它**自己吞掉失败**（400 → 指引卡、失败 → 结果行，返回 null 不抛），所以这里
    // 没有 catch——写了也只是死码（工单 02 评审整改）。
    await flashRunShared({
      dir,
      platform: hwcheckUI.project ? hwcheckUI.project.platform : "",
      statusEl: $("hwcheck-flash-status"),
      resultEl: $("hwcheck-flash-result"),
      setBusy: () => { /* 本层已置 busy（按钮防重） */ },
    });
  } finally {
    hwcheckUI.busy = false;
    if (btn) { btn.disabled = false; btn.textContent = "烧录到板子"; }
  }
}

async function openHwcheckFolder(dir) {
  if (!dir) return;
  try {
    // 既有交付端点（工单 delivery-suite/01）：stm32 优先拉起 Keil、兜底文件夹；
    // mspm0 打开文件夹（CCS 手动导入）——文案与 fx/delivery.js 同一口径
    const data = await apiPost("/api/delivery/open-ide", { output_dir: dir });
    toast("info", (data && data.message) || "已打开工程");
  } catch (e) {
    toastError(e, "打开工程失败");
  }
}

export function initHwcheck() {
  hwcheckUI.parentDir = readStored(HWCHECK_PARENT_KEY);
  const parentInput = $("hwcheck-parent");
  if (parentInput) parentInput.value = hwcheckUI.parentDir;

  const platforms = $("hwcheck-platforms");
  if (platforms) {
    // 事件委托（innerHTML 全量重绘后仍有效）：点平台卡 → 换平台并清掉旧产物
    // （旧产物是另一块板子的 main.c，留着会误导）。
    platforms.addEventListener("click", (e) => {
      const card = e.target.closest("[data-hwcheck-platform]");
      if (!card) return;
      const before = hwcheckUI.platform;
      Object.assign(hwcheckUI, hwcheckSelectPlatform(
        hwcheckPlatforms(), hwcheckUI, card.dataset.hwcheckPlatform));
      if (hwcheckUI.platform !== before) {
        hwcheckUI.preview = "";
        hwcheckUI.outputHint = "";
        hwcheckUI.wiring = null;          // 换板 = 旧接线表作废（脚不一样）
        hwcheckUI.sections = [];          // 换板 = 旧检测计划作废（配方按平台分）
        hwcheckUI.unspecialized = [];
        hwcheckUI.console = null;         // 同理：命令字符也按平台 / 配方给
        hwcheckUI.wiringError = "";
      }
      renderHwcheckPanel();
      refreshHwcheckView();               // 新平台的接线表 / 冲突立刻跟上
    });
    platforms.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      const card = e.target.closest("[data-hwcheck-platform]");
      if (!card) return;
      e.preventDefault();
      card.click();
    });
  }
  const channels = $("hwcheck-channels");
  if (channels) {
    // 通道勾选走委托（工单 02 起通道清单可能变长，逐个绑定会漏）；
    // 通道是渲染输入 → 改了就把旧预览清掉（旧文本是另一种形态的 main.c），
    // 并重取板侧视图（通道模块自己也会占脚、也会撞脚）。
    channels.addEventListener("change", (e) => {
      const input = e.target.closest("[data-hwcheck-channel]");
      if (!input) return;
      Object.assign(hwcheckUI, hwcheckPickState(
        hwcheckUI, input.dataset.hwcheckChannel, input.checked));
      hwcheckUI.preview = "";
      hwcheckUI.outputHint = "";
      hwcheckUI.wiring = null;
      hwcheckUI.sections = [];          // 通道变了 = 工程模块集变了，计划重取
      hwcheckUI.unspecialized = [];
      hwcheckUI.console = null;         // 命令表也一样（有没有串口决定能不能复测）
      hwcheckUI.wiringError = "";
      // 通道变了：生成前引导（mspm0 双通道会撞脚）要跟着变
      renderHwcheckChannelNote();
      renderHwcheckOutput();
      refreshHwcheckView();
    });
  }

  // —— 器件挑选（工单 03）：搜索框 / 卡片网格（点卡片 = 加一件）/ chips（点 = 去掉）——
  const deviceSearch = $("hwcheck-device-search");
  if (deviceSearch) {
    deviceSearch.addEventListener("input", () => {
      hwcheckUI.deviceQuery = deviceSearch.value || "";
      renderHwcheckDevices();
    });
  }
  const deviceGrid = $("hwcheck-device-grid");
  if (deviceGrid) {
    // 与生成页模块网格同一套委托语义：详情按钮优先（开说明弹窗），
    // 卡片本体 = 加一件器件。平台用**本栏目自己的**（生成页的平台可能不同）。
    deviceGrid.addEventListener("click", (e) => {
      const infoBtn = e.target.closest(".mc-info");
      if (infoBtn) {
        openModuleInfo(infoBtn.dataset.info, hwcheckUI.platform);
        return;
      }
      const card = e.target.closest("[data-add]");
      if (!card) return;
      addHwcheckDevice(card.dataset.add);
    });
  }
  const deviceChips = $("hwcheck-device-chips");
  if (deviceChips) {
    // 说明按钮走既有委托（捕获阶段拦，否则会连带把 chip 从工程里移除）
    bindModuleInfoEntry(deviceChips, () => hwcheckUI.platform);
    deviceChips.addEventListener("click", (e) => {
      const chip = e.target.closest("[data-remove]");
      if (chip) addHwcheckDevice(chip.dataset.remove, false);
    });
  }
  const preview = $("btn-hwcheck-preview");
  if (preview) preview.addEventListener("click", previewHwcheck);
  const generate = $("btn-hwcheck-generate");
  if (generate) generate.addEventListener("click", generateHwcheck);

  if (parentInput) {
    parentInput.addEventListener("change", () => {
      hwcheckUI.parentDir = parentInput.value.trim();
      writeStored(HWCHECK_PARENT_KEY, hwcheckUI.parentDir);
      loadHwcheckRecent();
    });
  }
  const pick = $("btn-hwcheck-pick-parent");
  if (pick) {
    pick.addEventListener("click", async () => {
      try {
        const data = await apiPost("/api/pick-directory", {});
        if (!data || !data.path) return;   // 用户取消：不覆盖输入框
        hwcheckUI.parentDir = String(data.path);
        if (parentInput) parentInput.value = hwcheckUI.parentDir;
        writeStored(HWCHECK_PARENT_KEY, hwcheckUI.parentDir);
        loadHwcheckRecent();
      } catch (e) {
        toastError(e, "选择文件夹失败");
      }
    });
  }

  const project = $("hwcheck-project");
  if (project) {
    project.addEventListener("click", (e) => {
      const compile = e.target.closest("[data-hwcheck-compile]");
      if (compile) {
        runHwcheckCompile(compile.dataset.hwcheckCompile, compile);
        return;
      }
      const flash = e.target.closest("[data-hwcheck-flash]");
      if (flash) {
        runHwcheckFlash(flash.dataset.hwcheckFlash, flash);
        return;
      }
      const open = e.target.closest("[data-hwcheck-open]");
      if (open) openHwcheckFolder(open.dataset.hwcheckOpen);
    });
  }
  const checklist = $("hwcheck-checklist");
  if (checklist) {
    checklist.addEventListener("change", (e) => {
      const input = e.target.closest("[data-hwcheck-check]");
      if (!input || !hwcheckUI.project) return;
      const key = hwcheckChecklistKey(hwcheckUI.project.outputDir);
      writeStored(key, hwcheckChecklistToggle(
        readStored(key), input.dataset.hwcheckCheck, input.checked));
      hwcheckUI.checklistChecked = hwcheckCheckedIds(readStored(key));
      renderHwcheckChecklist();
      // 落服务端一份（工单 08）：刷新 / 换机器回显靠它；本地备忘退成兜底
      syncHwcheckChecklist();
    });
  }
  // —— 现象回填 + AI 排障（工单 08）：唯一的 LLM 入口 ——
  const symptom = $("hwcheck-symptom");
  if (symptom) {
    symptom.addEventListener("input", () => {
      hwcheckUI.symptom = symptom.value;
      renderHwcheckAdvice();   // 按钮的可用性跟着"填没填"变
    });
  }
  const triage = $("btn-hwcheck-triage");
  if (triage) triage.addEventListener("click", submitHwcheckTriage);
  const recent = $("hwcheck-recent");
  if (recent) {
    recent.addEventListener("click", (e) => {
      const row = e.target.closest("[data-hwcheck-open-project]");
      if (row) restoreHwcheckProject(row.dataset.hwcheckOpenProject);
    });
  }

  renderHwcheckPanel();
  // 刷新回显：上次看的那个检测工程按服务端真源读回来（清单内容与勾选态都回来）
  const last = readStored(HWCHECK_LAST_DIR_KEY);
  if (last) restoreHwcheckProject(last);
  loadHwcheckRecent();
}
