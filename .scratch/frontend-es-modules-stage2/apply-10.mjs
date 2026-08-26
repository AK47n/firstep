// 阶段 2 工单 10：设置 tab 迁 ui/settings.js（区段 A：加载/保存/视觉/体检/
// 价格/时段/单价收集/工作流渲染；区段 B：设置折叠 glue；refreshState 随唯一
// 调用点迁入 + setSettingsDeps 接缝（toolchains + renderToolchainStatus 宿主）。
// 删除段（物理升序，内容锚点寻址）：refreshState 定义 / 设置页区段 A /
// 设置页折叠区段 B。host 顶部 import 追加 settings.js 代理 5 名；usage.js 代理
// 行裁至 renderUsageStats（其余名随 12/10 迁出后 host 零使用）。全程 CRLF 感知。
import { readFileSync, writeFileSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };

if (lines.some((l) => l.includes('from "/js/ui/settings.js"'))) throw new Error("settings import already present");

// ---- 1) host import：topic import 之后追加；usage.js 代理行裁剪
{
  const ti = must(lines.findIndex((l) => l.includes('from "/js/ui/topic.js"')), "topic import");
  lines.splice(ti + 1, 0,
    'import { loadSettings, loadRecentWorkflows, initSettingsCollapse, renderPriceReference, setSettingsDeps } from "/js/ui/settings.js";');
}
{
  const ui = must(lines.findIndex((l) => l.includes('from "/js/ui/usage.js"')), "usage import");
  if (!lines[ui].includes("renderUsageStats")) throw new Error("renderUsageStats not in usage import?");
  lines[ui] = 'import { renderUsageStats } from "/js/ui/usage.js";';
}

// ---- 2) refreshState 定义 → 注记（随唯一调用点迁入 settings.js）
{
  const a = must(lines.findIndex((l) => l.startsWith("async function refreshState() {")), "refreshState");
  let e = a;
  while (e < lines.length && lines[e] !== "}") e++;
  if (e >= lines.length) throw new Error("refreshState end not found");
  const removed = lines.slice(a, e + 1).join(eol);
  for (const n of ["refreshState", "renderToolchainStatus", "renderPlatforms", "renderModulePool"]) {
    if (!removed.includes(n)) throw new Error("refreshState body missing " + n);
  }
  const note = [
    "// 保存设置后的状态重载（refreshState）已随其唯一调用点（btn-save-settings）",
    "// 迁至 static/js/ui/settings.js（阶段 2 工单 10）：state / modules 重拉 +",
    "// 工具链重算（经 setSettingsDeps 接缝写宿主 toolchains +",
    "// renderToolchainStatus——工单 16 迁出后改静态 import）+ 平台卡 / 模块池重渲染。",
    "",
  ];
  lines.splice(a, e - a + 1, ...note);
}

// ---- 3) 设置页区段 A（设置页头 → btn-refresh-recent-wf 监听末）→ 注记
{
  const a = must(lines.findIndex((l) => l === "// 设置页"), "settings header");
  const dashA = a - 1;
  if (!lines[dashA].startsWith("// ------")) throw new Error("dash before settings header not found");
  const b = must(lines.findIndex((l) => l.startsWith('$("btn-refresh-recent-wf").addEventListener("click", loadRecentWorkflows);')), "btn-refresh-recent-wf");
  const removed = lines.slice(dashA, b + 1).join(eol);
  for (const n of ["loadSettings", "visionZhipuMask", "VISION_PRESETS", "syncVisionProviderFromFields", "applyVisionPreset", "envCheckRun", "renderPriceReference", "periodPlaceholders", "collectLlmPrices", "renderRecentWorkflows", "loadRecentWorkflows"]) {
    if (!new RegExp("(function|const|let)\\s+" + n + "\\b").test(removed)) throw new Error("missing " + n);
  }
  if (!removed.includes("btn-save-settings") || !removed.includes("btn-env-check")) throw new Error("settings listeners missing");
  const note = [
    "// ---------------------------------------------------------------------------",
    "// 设置页：配置加载 / 保存 / 视觉预设 / 环境体检 / 价格参考 / 单价收集 / 折叠",
    "// 与最近工作流（全部已迁 ui/settings.js）",
    "// ---------------------------------------------------------------------------",
    "// 已迁至 static/js/ui/settings.js（阶段 2 工单 10）：loadSettings /",
    "// syncVisionProviderFromFields / applyVisionPreset / envCheckRun /",
    "// renderPriceReference / periodPlaceholders / collectLlmPrices /",
    "// renderRecentWorkflows / loadRecentWorkflows / refreshState + 视觉预设与",
    "// 全部按钮监听（set-vision-provider / btn-vision-selfcheck / btn-env-check /",
    "// price-period / set-local-llm-model / btn-save-settings /",
    "// btn-refresh-recent-wf）。单价表（llmPricesDefaults / setLlmPricesDefaults）",
    "// 属 ui/usage.js（工单 04 前置拆分），本模块经 import 读写活绑定；",
    "// 纯件在 fx/settings.js / fx/workflow.js / fx/env.js。",
    "// host 页签分发器 / 启动区经顶部 import 调 loadSettings / loadRecentWorkflows /",
    "// initSettingsCollapse（见 import 行与启动区）。",
    "",
  ];
  lines.splice(dashA, b - dashA + 1, ...note);
}

// ---- 4) 设置页折叠 glue 区段（设置页折叠头 → LLM 用量统计区段前）→ 注记
{
  const a = must(lines.findIndex((l) => l === "// 设置页折叠（工单 settings-infoarch/01-03）：整卡折叠 + 默认收起次要项 +"), "settings-collapse header");
  const dashA = a - 1;
  if (!lines[dashA].startsWith("// ------")) throw new Error("dash before settings-collapse not found");
  const b = must(lines.findIndex((l) => l.startsWith("// LLM 用量统计（工单 ui-polish-5/02）")), "usage note");
  const dashB = b - 1;
  if (!lines[dashB].startsWith("// ------")) throw new Error("dash before usage note not found");
  const removed = lines.slice(dashA, dashB).join(eol);
  if (!removed.includes("function saveSettingsCollapse(") || !removed.includes("function initSettingsCollapse(")) throw new Error("collapse glue missing");
  const note = [
    "// ---------------------------------------------------------------------------",
    "// 设置页折叠（工单 settings-infoarch/01-03）：saveSettingsCollapse /",
    "// initSettingsCollapse 已迁至 static/js/ui/settings.js（阶段 2 工单 10）；",
    "// 纯件在 fx/settings.js（SETTINGS_COLLAPSE_KEY / parseSettingsCollapse /",
    "// effectiveCollapsed / settingsMasterLabel / settingsSectionHead /",
    "// applySettingsCollapseState 等）。host 启动区 5821 经 import 调用。",
    "",
  ];
  lines.splice(dashA, dashB - dashA, ...note);
}

// ---- 5) 接缝注册：setSettingsDeps（host 写 toolchains + renderToolchainStatus）
{
  const i = must(lines.findIndex((l) => l.startsWith('setOnStepChange(() =>')), "setOnStepChange registration");
  lines.splice(i + 1, 0,
    "setSettingsDeps({ applyToolchains: (ts) => { toolchains = ts; renderToolchainStatus(); } });");
}

// ---- 校验
const out = lines.join(eol);
for (const n of ["loadSettings", "syncVisionProviderFromFields", "applyVisionPreset", "envCheckRun", "renderPriceReference", "periodPlaceholders", "collectLlmPrices", "renderRecentWorkflows", "loadRecentWorkflows", "saveSettingsCollapse", "initSettingsCollapse", "refreshState"]) {
  if (new RegExp("(function|const|let)\\s+" + n + "\\b").test(out)) throw new Error("residual definition of " + n);
}
if (/^(const|let)\s+(visionZhipuMask|visionApplyingPreset|VISION_PRESETS|VISION_HINTS)$/m.test(out)) throw new Error("residual vision state");
for (const frag of ['loadSettings(); loadRecentWorkflows(); renderUsageStats();', 'initSettingsCollapse();', 'from "/js/ui/settings.js"', 'import { renderUsageStats } from "/js/ui/usage.js";', 'setSettingsDeps({ applyToolchains: (ts) => { toolchains = ts; renderToolchainStatus(); } });']) {
  if (!out.includes(frag)) throw new Error("host call site / import / seam vanished: " + frag);
}
if (out.includes('setLlmPricesDefaults(')) throw new Error("setLlmPricesDefaults call still in host (moved)");

writeFileSync(p, out, "utf8");
console.log("OK: settings cluster moved; host rewired; lines now", lines.length);
