// ui/hwcheck-actions.js — 硬件检测栏目的**动作与请求**（工单 hwcheck-hygiene/11）：
// 预览 / 生成 / 采纳 / 恢复 / 最近 / 编译 / 烧录 / 打开目录 / 清单同步 / 排障提交 /
// 带入生成页，加上它们在入口里那十处委托的处理分支。
//
// 正文由 `ui/hwcheck.js` 整段搬来（函数体与注释逐字保留；下沉进来的处理分支只左移了缩进）。
// 判据全在服务端与 fx 纯件里，本件只做"读状态 / 发请求 / 调渲染"三件事。
//
// 依赖方向（单源 = ui/hwcheck-core.js 头部）：本件 → 核心件。**不 import 入口、也不
// import 器件件**。复用既有执行体的三条边（编译 / 烧录 / 切页签）照旧。

import {
  $,
  apiGet,
  apiPost,
  toast,
  toastError,
} from "/js/app.js";
import { compileErrorRowsHTML, compileStatusClass, compileStatusText } from "/js/fx/code-compile.js";
import { hwcheckHandoffResultText } from "/js/fx/hwcheck-handoff.js";
import { hwcheckConsoleState, hwcheckCustomState, hwcheckSectionsState } from "/js/fx/hwcheck-plan.js";
import {
  HWCHECK_LAST_DIR_KEY,
  HWCHECK_PARENT_KEY,
  hwcheckBoardState,
  hwcheckCheckedIds,
  hwcheckChecklistKey,
  hwcheckChecklistToggle,
  hwcheckGeneratePayload,
  hwcheckProjectState,
} from "/js/fx/hwcheck-project.js";
import {
  hwcheckCanPreview,
  hwcheckPickState,
  hwcheckPreviewState,
  hwcheckRequestPayload,
  hwcheckSelectPlatform,
} from "/js/fx/hwcheck-state.js";
import {
  hwcheckAdviceState,
  hwcheckCanTriage,
  hwcheckChecklistPayload,
  hwcheckChecklistState,
  hwcheckRecordState,
  hwcheckTriagePayload,
} from "/js/fx/hwcheck-triage.js";
import { hwcheckDevicePick } from "/js/fx/hwcheck-wiring.js";
import { runCompileOnceCore } from "/js/ui/fix-center-core.js";
import { flashRunShared } from "/js/ui/flash.js";
import { addModulesFromHandoff, openModuleInfo } from "/js/ui/generate-recommend.js";
import { gotoNavTab } from "/js/ui/goto-nav.js";
import {
  applyDroppedDevices,
  hwcheckHandoff,
  hwcheckPlatforms,
  hwcheckUI,
  readStored,
  renderHwcheckAdvice,
  renderHwcheckChannelNote,
  renderHwcheckChecklist,
  renderHwcheckConsole,
  renderHwcheckCustom,
  renderHwcheckDevices,
  renderHwcheckHandoff,
  renderHwcheckOutput,
  renderHwcheckPanel,
  renderHwcheckPlatforms,
  renderHwcheckProject,
  renderHwcheckRecent,
  renderHwcheckSections,
  renderHwcheckWiring,
  selectorValue,
  setPendingFocus,
  writeStored,
} from "/js/ui/hwcheck-core.js";
// handoffToGenerate()：把这批器件并进生成页的已选清单，再切到生成页。
//
// 三步的顺序本身是判据：**先算计划**（带入块上那几句理由说的就是这一批）→
// **再并入**（走推荐簇 A 的入口——选择集只有它一个写者）→ **最后切页签**并落到
// 已选清单上（不切的话用户在检测页看着像没反应）。
// 一件都带不过去时**留在本页**：理由已经写在带入块里，不切走、也不弹"成功"。
// 那句话本身也由 fx 拼（`hwcheckHandoffResultText`）——本层不自己写文案。
export function handoffToGenerate() {
  const plan = hwcheckHandoff();
  if (!plan.carry.length) {
    renderHwcheckHandoff();   // 兜底重画：按钮本来是灰的，状态变了也得跟得上
    return;
  }
  const { added, already } = addModulesFromHandoff(plan.carry);
  gotoNavTab("generate", "selected-list");
  toast("ok", hwcheckHandoffResultText(added, already));
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
//   ③ 失败清**整份**（板侧视图 + main.c）并归到 `previewError`（工单 hwcheck-hardening/07）：
//      主程序是**按所选器件**渲染的（`render_main_c(config, sections, generic, custom)`），
//      所以失败之后留着的那份属于上一组器件——照它去编译烧录就是烧错东西。
//      （旧注释说"检测程序只依赖平台与通道"，那个前提不成立，已更正。）
let hwcheckViewBusy = false;
let hwcheckViewPending = false;

function hwcheckSelectionKey() {
  return JSON.stringify(hwcheckRequestPayload(hwcheckUI));
}

export async function refreshHwcheckView() {
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
      Object.assign(hwcheckUI, hwcheckCustomState(hwcheckUI, payload));
      Object.assign(hwcheckUI, hwcheckConsoleState(hwcheckUI, payload));
      // 已被删掉的自建件：服务端这一趟摘掉了谁（工单 ci-gate-fixes/09）——先对齐选择集，
      // 下面那串 render 才会画出一致的 chips 与说明条。
      applyDroppedDevices(payload);
      hwcheckUI.previewError = "";
    }
  } catch (e) {
    if (hwcheckSelectionKey() === requestKey) {
      // 这一趟**整份**都没拿到（预览 = 主程序 + 板侧视图 + 逐件小节 + 命令表，同一个请求）：
      // 板侧视图清空，但错误归到 `previewError`——它是"检测程序预览失败"，不是"接线表取不到"
      // （把那句写在这里会把学生引去查线，见工单 hwcheck-hardening/07）。
      hwcheckUI.wiring = null;
      hwcheckUI.sections = [];
      hwcheckUI.unspecialized = [];
      hwcheckUI.custom = [];
      hwcheckUI.console = null;
      hwcheckUI.consoleNote = "";
      // ⚠ 上次的 main.c 必须一起清掉（工单 hwcheck-hardening/07 更正）：主程序是**按所选器件**
      // 渲染的（`render_main_c(config, sections, generic, custom)`），所以失败之后留着的那份
      // 属于**上一组器件**——照它去编译烧录就是烧错东西。此前这里不清，理由是"检测程序只依赖
      // 平台与通道"，那个前提不成立。
      hwcheckUI.preview = "";
      hwcheckUI.outputHint = "";
      hwcheckUI.previewError = e && e.message ? e.message : String(e);
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
  renderHwcheckCustom();
  renderHwcheckConsole();   // 命令表也随载荷更新（真机验收抓到的漏渲染）
}

export async function previewHwcheck() {
  if (!hwcheckCanPreview(hwcheckUI) || hwcheckUI.busy) return;
  const box = $("hwcheck-output");
  if (box) box.innerHTML = '<div class="muted">正在渲染检测程序…</div>';
  // 进行中禁用（工单 hwcheck-hygiene/06）：与生成那条路同款——按钮按住时看得出来，
  // 不是"点了没反应"（上面那道 busy 早退是兜底，不是给人看的）。
  hwcheckUI.busy = true;
  renderHwcheckPlatforms();
  try {
    await refreshHwcheckView();
  } finally {
    hwcheckUI.busy = false;
    renderHwcheckPlatforms();
  }
}

// addHwcheckDevice(slug, on)：加 / 去一件器件 → 重绘挑选面 + 重取板侧视图。
// 选器件本身就是"我想看它怎么接"——所以这里顺手刷新一次（本地请求，零 LLM）。
// 组清单一起带上：同组互斥 = 单选交换（工单 05），判据来自服务端载荷的
// exclusive_groups（还没拿到时为空数组 = 老行为"只加不换"，提示会兜底说明）。
export function addHwcheckDevice(slug, on = true) {
  Object.assign(hwcheckUI, hwcheckDevicePick(
    hwcheckUI, slug, on, hwcheckUI.exclusiveGroups));
  renderHwcheckDevices();
  refreshHwcheckView();
}

// generateHwcheck()：生成检测工程（后端确定性渲染 + 既有生成内核）。
// 成功 = 新子目录 + 一块工程面板 + 一份上板清单；失败 = 中文理由原样带出
// （含 mspm0 默认撞脚这类"引擎如实拒绝"）。
export async function generateHwcheck() {
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
    // 生成这一趟同样可能摘掉"已经不在器件库"的自建件（工单 ci-gate-fixes/09）：
    // adoptProject 会按工程上下文回填器件集（可能又把它带回来），所以**排在它之后**。
    applyDroppedDevices(payload);
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
export async function restoreHwcheckProject(dir) {
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

export async function loadHwcheckRecent() {
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
export async function submitHwcheckTriage() {
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

// —— 事件委托的处理分支（工单 hwcheck-hygiene/11）——
// 由入口 `ui/hwcheck.js` 的接线调用：这里只放「点了之后做什么」，选择器的归属
// 仍在入口的接线行上（一处只写一遍）。

// handlePlatformClick(e)：点平台卡 → 换平台并清掉旧产物（旧产物是另一块板子的 
// main.c，留着会误导）；换成功再重取一次板侧视图。
export function handlePlatformClick(e) {
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
  }
  renderHwcheckPanel();
  refreshHwcheckView();               // 新平台的接线表 / 冲突立刻跟上
}

// handleChannelChange(e)：勾 / 取消一个输出通道——通道是渲染输入，改了就把旧预览清掉，
// 并重取板侧视图（通道模块自己也会占脚、也会撞脚）。
export function handleChannelChange(e) {
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
  hwcheckUI.previewError = "";      // 换通道 = 重新渲染输入，旧错误不再适用
  // 通道变了：生成前引导（mspm0 双通道会撞脚）要跟着变
  renderHwcheckChannelNote();
  renderHwcheckOutput();
  refreshHwcheckView();
}

// activateHwcheckDeviceCard(target)：器件网格里「点一张卡 = 加一件」（卡片本体；
// 详情按钮优先，见 handleDeviceGridClick）。重绘后把焦点送到**这一件的结果**上（加进之后它在 
// chips 里，卡片本身会从「还没选」的池子里消失）。
function activateHwcheckDeviceCard(target) {
  const card = target.closest("[data-add]");
  if (!card) return;
  // 重绘后把焦点送到**这一件的结果**上（工单 hwcheck-hygiene/06）：加进之后它
  // 在 chips 里（卡片本身会从"还没选"的池子里消失），所以在 chip 上落焦点。
  setPendingFocus(`#hwcheck-device-chips [data-remove="${selectorValue(card.dataset.add)}"]`);
  addHwcheckDevice(card.dataset.add);
}

// handleDeviceGridClick(e)：与生成页模块网格同一套委托语义——详情按钮优先（开说明弹窗）
// ，卡片本体 = 加一件器件。平台用**本栏目自己的**（生成页的平台可能不同）。
export function handleDeviceGridClick(e) {
  const infoBtn = e.target.closest(".mc-info");
  if (infoBtn) {
    openModuleInfo(infoBtn.dataset.info, hwcheckUI.platform);
    return;
  }
  if (e.target.closest("[data-add]")) activateHwcheckDeviceCard(e.target);
}

// handleDeviceGridKeydown(e)：键盘同等可达（工单 hwcheck-hygiene/06）——卡片是role=button 
// tabindex=0；详情按钮是真 <button>（浏览器自己把 Enter/Space变成 click），排掉免得开两次。
export function handleDeviceGridKeydown(e) {
  if (e.key !== "Enter" && e.key !== " " && e.key !== "Spacebar") return;
  if (e.target.closest && e.target.closest(".mc-info")) return;
  e.preventDefault();
  if (e.target.closest("[data-add]")) activateHwcheckDeviceCard(e.target);
}

// handleDeviceChipsClick(e)：点 chip 上的 ✕ = 从这次检测里去掉这一件；移除之后 
// chip 就不在了，焦点落到网格里那张卡上。
export function handleDeviceChipsClick(e) {
  const chip = e.target.closest("[data-remove]");
  if (chip) {
    // 移除之后 chip 就不在了：焦点落到**网格里那张卡**上（它刚回到"还没选"的池子）
    setPendingFocus(`#hwcheck-device-grid [data-add="${selectorValue(chip.dataset.remove)}"]`);
    addHwcheckDevice(chip.dataset.remove, false);
  }
}

// handleDeviceChipsKeydown(e)：chip 是 role=button tabindex=0（工单 06），Enter 
// / Space 与点它同义（说明按钮自己会响应，排掉）。
export function handleDeviceChipsKeydown(e) {
  if (e.key !== "Enter" && e.key !== " " && e.key !== "Spacebar") return;
  if (e.target.closest && e.target.closest("[data-mod-info]")) return;   // 说明按钮自己会响应
  const chip = e.target.closest("[data-remove]");
  if (!chip) return;
  e.preventDefault();
  setPendingFocus(`#hwcheck-device-grid [data-add="${selectorValue(chip.dataset.remove)}"]`);
  addHwcheckDevice(chip.dataset.remove, false);
}

// handleParentChange(parentInput)：输出父目录改了——记住它（本地备忘）并重载最近列表。
export function handleParentChange(parentInput) {
  hwcheckUI.parentDir = parentInput.value.trim();
  writeStored(HWCHECK_PARENT_KEY, hwcheckUI.parentDir);
  loadHwcheckRecent();
}

// pickHwcheckParent(parentInput)：「选择文件夹」（服务端原生对话框）——用户取消（没有 
// path）不覆盖输入框。
export async function pickHwcheckParent(parentInput) {
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
}

// handleProjectClick(e)：工程面板上的三个动作——编译 / 烧录 / 打开工程目录（按钮由调用方传进来，
// 不用选择器反查：Windows 路径里的 `\U` 在 JS 字符串里是转义序列）。
export function handleProjectClick(e) {
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
}

// handleChecklistChange(e)：上板清单勾选——本地备忘写一份（离线兜底）、服务端也落一份（刷新 
// / 换机器回显的真源），并保持焦点在刚勾的那一项上。
export function handleChecklistChange(e) {
  const input = e.target.closest("[data-hwcheck-check]");
  if (!input || !hwcheckUI.project) return;
  const key = hwcheckChecklistKey(hwcheckUI.project.outputDir);
  // 重绘后焦点回**刚勾的那一项**（工单 hwcheck-hygiene/06）：清单整块 innerHTML
  // 重绘会把复选框换掉、焦点掉回 body——学生连续勾十几项时每次都要重新找位置。
  setPendingFocus(`[data-hwcheck-check="${selectorValue(input.dataset.hwcheckCheck)}"]`);
  writeStored(key, hwcheckChecklistToggle(
    readStored(key), input.dataset.hwcheckCheck, input.checked));
  hwcheckUI.checklistChecked = hwcheckCheckedIds(readStored(key));
  renderHwcheckChecklist();
  // 落服务端一份（工单 08）：刷新 / 换机器回显靠它；本地备忘退成兜底
  syncHwcheckChecklist();
}
