// ui/hwcheck.js — 硬件检测栏目的 DOM 胶水（工单 module-hwcheck/01）。
//
// 单向依赖：ui → fx / app（纯件在 fx/hwcheck.js，本文件只读状态、写 DOM、
// 发请求）。栏目独立于赛题工作流：不读题面、不读已选模块、不写最近工程记录。
// 预览走 POST /api/hwcheck/preview（后端确定性渲染，零 LLM）——**不落盘**，
// 落盘（生成工程 / 编译 / 烧录）是后续工单的事。
import { $, apiPost, state } from "/js/app.js";
import { chosenPlatform } from "/js/ui/generate-recommend.js";
import {
  hwcheckPlatformState, hwcheckSelectPlatform, hwcheckPickState,
  hwcheckRequestPayload, hwcheckCanPreview, hwcheckPlatformCardsHTML,
  hwcheckErrorHTML, hwcheckEmptyHTML, hwcheckPanelHTML, hwcheckCodeTarget,
  hwcheckPreviewState,
} from "/js/fx/hwcheck.js";

// 本栏目自己的状态（与生成流程零共享）：选中平台 + 两个输出通道开关 +
// 最近一次预览的结果。首次进入时 platform 从全局当前平台继承（见
// hwcheckPlatformState），但**不依赖**它以后的变化。
const hwcheckUI = {
  platform: "",
  debug_uart: true,
  oled: true,
  preview: "",
  outputHint: "",
  seeded: false,
};

function hwcheckPlatforms() {
  return (state && state.platforms) || [];
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
  const preview = $("btn-hwcheck-preview");
  if (preview) preview.disabled = !hwcheckCanPreview(hwcheckUI);
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

function renderHwcheckError(message) {
  $("hwcheck-output").innerHTML = hwcheckErrorHTML(message);
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
    renderHwcheckError(e && e.message ? e.message : String(e));
  }
}

export function renderHwcheckPanel() {
  renderHwcheckPlatforms();
  renderHwcheckOutput();
}

export function initHwcheck() {
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
    // 通道勾选走委托（工单 02 起通道清单可能变长，逐个绑定会漏）
    channels.addEventListener("change", (e) => {
      const input = e.target.closest("[data-hwcheck-channel]");
      if (!input) return;
      Object.assign(hwcheckUI, hwcheckPickState(
        hwcheckUI, input.dataset.hwcheckChannel, input.checked));
    });
  }
  const preview = $("btn-hwcheck-preview");
  if (preview) preview.addEventListener("click", previewHwcheck);
  renderHwcheckPanel();
}
