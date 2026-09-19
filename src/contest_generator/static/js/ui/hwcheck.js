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
import { flashRunShared } from "/js/ui/flash.js";
import { runCompileOnceCore } from "/js/ui/fix-center-core.js";
import {
  compileStatusText, compileStatusClass, compileErrorRowsHTML,
} from "/js/fx/code-compile.js";
import {
  hwcheckPlatformState, hwcheckSelectPlatform, hwcheckPickState,
  hwcheckRequestPayload, hwcheckCanPreview, hwcheckPlatformCardsHTML,
  hwcheckErrorHTML, hwcheckGenerateErrorHTML, hwcheckEmptyHTML, hwcheckPanelHTML,
  hwcheckCodeTarget, hwcheckPreviewState, hwcheckPlatformLabel,
  hwcheckGeneratePayload, hwcheckChecklistKey, hwcheckCheckedIds,
  hwcheckChecklistToggle, hwcheckChecklistHTML, hwcheckChecklistProgressHTML,
  hwcheckProjectState, hwcheckProjectPanelHTML, hwcheckProjectEmptyHTML,
  hwcheckRecentHTML, hwcheckRecentEmptyHTML, hwcheckChannelNoteHTML,
  HWCHECK_PARENT_KEY, HWCHECK_LAST_DIR_KEY,
} from "/js/fx/hwcheck.js";

// 本栏目自己的状态（与生成流程零共享）：选中平台 + 两个输出通道开关 +
// 输出父目录 + 最近一次预览/生成的结果 + 上板清单勾选态。
const hwcheckUI = {
  platform: "",
  debug_uart: true,
  oled: true,
  parentDir: "",
  preview: "",
  outputHint: "",
  project: null,      // 当前正在看的检测工程（生成或回读来的）
  checklistChecked: [],
  recent: [],
  generateError: "",
  busy: false,
  seeded: false,
};

function hwcheckPlatforms() {
  return (state && state.platforms) || [];
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

export function renderHwcheckPanel() {
  renderHwcheckPlatforms();
  renderHwcheckChannelNote();
  renderHwcheckOutput();
  renderHwcheckProject();
  renderHwcheckChecklist();
  renderHwcheckRecent();
}

// adoptProject(payload, dir)：把一次生成 / 回读的结果放到页面上——同时记住
// "上次看的是哪个目录"，并按该目录取出本地勾选态。
function adoptProject(payload, dir) {
  Object.assign(hwcheckUI, hwcheckProjectState(hwcheckUI, payload));
  Object.assign(hwcheckUI, hwcheckPreviewState(hwcheckUI, payload));
  hwcheckUI.checklistChecked = hwcheckCheckedIds(
    readStored(hwcheckChecklistKey(dir)));
  hwcheckUI.generateError = "";
  writeStored(HWCHECK_LAST_DIR_KEY, dir);
}

async function previewHwcheck() {
  if (!hwcheckCanPreview(hwcheckUI)) return;
  const box = $("hwcheck-output");
  box.innerHTML = '<div class="muted">正在渲染检测程序…</div>';
  try {
    const payload = await apiPost("/api/hwcheck/preview", hwcheckRequestPayload(hwcheckUI));
    Object.assign(hwcheckUI, hwcheckPreviewState(hwcheckUI, payload));
    renderHwcheckOutput();
  } catch (e) {
    hwcheckUI.preview = "";
    hwcheckUI.outputHint = "";
    $("hwcheck-output").innerHTML = hwcheckErrorHTML(e && e.message ? e.message : String(e));
  }
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
async function restoreHwcheckProject(dir) {
  if (!dir) return;
  try {
    const payload = await apiGet(
      "/api/hwcheck/project?output_dir=" + encodeURIComponent(dir));
    adoptProject(payload, dir);
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
      }
      renderHwcheckPanel();
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
    // 通道是渲染输入 → 改了就把旧预览清掉（旧文本是另一种形态的 main.c）。
    channels.addEventListener("change", (e) => {
      const input = e.target.closest("[data-hwcheck-channel]");
      if (!input) return;
      Object.assign(hwcheckUI, hwcheckPickState(
        hwcheckUI, input.dataset.hwcheckChannel, input.checked));
      hwcheckUI.preview = "";
      hwcheckUI.outputHint = "";
      // 通道变了：生成前引导（mspm0 双通道会撞脚）要跟着变
      renderHwcheckChannelNote();
      renderHwcheckOutput();
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
    });
  }
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
