// 阶段 2 工单 16：生成页「编译修复中心（fix center）」簇迁
// static/js/ui/generate-fix.js。
// ① 提取 index.html 2474-3039（修复中心 section 注释 + FIX_MAX_ROUNDS /
//    toolchains / fixLoop / lastFix* / fixSourceCache + 25 函数 + 5 监听器）→
//    拼装新模块（头部注释 + imports + 导出清单；fmtSeconds 纯函数剔除——迁
//    fx/generate.js；toolchains 改 export let + 新增 setToolchains setter）；
// ② index.html：删簇体→注记 + host import 行（generate-core 之后）+
//    setSettingsDeps 回调/init 两处写点改 setToolchains + setGenerateCoreDeps
//    注册行删除 + 2246 core import 行去 setGenerateCoreDeps；
// ③ ui/generate-core.js：接缝还原为静态 import（startFixCenter /
//    compileBanner / toolchains——工单 16 迁出后改静态 import 先例）；
// ④ ui/generate-recommend.js：头部注释更新（updateFixCenterAvailability 已
//    迁，A 仍经 host 注册的 clusterDeps 闭包调用——与工单 13 pins 同构）。
// 全程 CRLF 感知；模块文件 LF（与既有 ui/*.js 一致）。
import { readFileSync, writeFileSync, existsSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
const mod = "src/contest_generator/static/js/ui/generate-fix.js";
const coreMod = "src/contest_generator/static/js/ui/generate-core.js";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };
if (lines.some((l) => l.includes('from "/js/ui/generate-fix.js"'))) throw new Error("import already present");
if (existsSync(mod)) throw new Error("module file already exists: " + mod);

// ---- 1) 定位并提取簇体（修复中心 section 头 → 修订与深化 section 头，不含后者） ----
const hFix = must(lines.findIndex((l) => l.startsWith("// 生成页：10. 修复中心（工单 autocompile-loop/01）")), "fix header");
const dashFix = hFix - 1;
if (!lines[dashFix].startsWith("// ------")) throw new Error("dash before fix header not found");
const hRevise = must(lines.findIndex((l) => l.startsWith("// 修订与深化阶段卡（工单 revise-deepen/05）")), "revise header");
const dashRevise = hRevise - 1;
if (!lines[dashRevise].startsWith("// ------")) throw new Error("dash before revise header not found");
const body = lines.slice(dashFix, dashRevise);
const bodyTxt0 = body.join(eol);
for (const n of ["FIX_MAX_ROUNDS", "toolchains", "fixLoop", "lastFix", "lastFixDone",
  "fixSourceCache", "compileBanner", "renderCompileBanner", "fixKeyOf", "fixKeyBasename",
  "maincScrollToRange", "maincJumpToLine", "fixToggleSource", "fixRenderResults",
  "fixSetBusy", "fixCenterBusy", "renderToolchainStatus", "renderFixLLMTelemetry",
  "clearFixLLMTelemetry", "updateFixCenterAvailability", "fixHandleEvent",
  "runCompileOnce", "runFixOnce", "fixRounds", "startFixCenter", "continueFixCenter"]) {
  if (!new RegExp("function\\s+\\w*\\s*" + n + "\\(").test(bodyTxt0) && !new RegExp("const\\s+" + n + "\\b").test(bodyTxt0) && !new RegExp("let\\s+" + n + "\\b").test(bodyTxt0)) {
    throw new Error("cluster missing " + n);
  }
}
if (!bodyTxt0.includes('$("btn-fix-center").addEventListener("click", startFixCenter)')) throw new Error("btn-fix-center listener missing");
if (!bodyTxt0.includes('$("btn-fix-rollback").addEventListener("click", async () => {')) throw new Error("rollback listener missing");
if (!bodyTxt0.includes("fixLoop.resume = { errorText, lastSummary, lastFixDone }")) throw new Error("resume snapshot missing");
if (!bodyTxt0.includes("可点「继续修复」再来")) throw new Error("continue text missing");
if (bodyTxt0.includes("readinessState")) throw new Error("cluster must not contain readinessState");

// ---- 2) 微调（比逐字多两点）：toolchains 导出化 + setter；剔除 fmtSeconds（迁 fx） ----
let bodyTxt = bodyTxt0.replace(
  "let toolchains = { stm32: false, mspm0: false };  // /api/state 装载：平台 → 工具链可用",
  "export let toolchains = { stm32: false, mspm0: false };  // /api/state 装载：平台 → 工具链可用\n" +
  "export function setToolchains(v) { toolchains = v; }  // 写入经 setter（host init / 设置页工具链重算）");
if (bodyTxt === bodyTxt0) throw new Error("toolchains export tweak failed");
const fmtRe = /function fmtSeconds\(s\) \{   \/\/ 耗时展示：1 位小数（如 12\.3）\r?\n  const n = Number\(s\);\r?\n  return Number\.isFinite\(n\) && n >= 0 \? n\.toFixed\(1\) : "0\.0";\r?\n\}\r?\n\r?\n/;
if (!fmtRe.test(bodyTxt)) throw new Error("fmtSeconds block not found");
bodyTxt = bodyTxt.replace(fmtRe, "");
if (bodyTxt.includes("function fmtSeconds(")) throw new Error("fmtSeconds residual");

// ---- 3) 拼装 ui/generate-fix.js（LF；头部注释 + imports + 簇体 + 导出） ----
const header = [
  "// ui/generate-fix.js — 生成页 · 编译修复中心（工单 autocompile-loop/01 等",
  "// 全家桶：单次编译 / 修复循环 ≤3 轮 / 批继续 / 横幅四态 / 结果表 / telemetry /",
  "// 就绪度）DOM 胶水（阶段 2 工单 16，源自 index.html 生成页：10. 修复中心节）。",
  "//",
  "// 簇体全量迁入：FIX_MAX_ROUNDS / toolchains（主写簇：export let + setToolchains",
  "// setter——host init 与设置页重算经 setter 写，其余读方 import）/ fixLoop /",
  "// lastFix* / fixSourceCache + compileBanner / renderCompileBanner / fmtSeconds",
  "//（纯函数→已迁 fx/generate.js，本模块 import）/ fixKeyOf / fixKeyBasename /",
  "// maincScrollToRange / maincJumpToLine / fixToggleSource / fixRenderResults /",
  "// fixSetBusy / fixCenterBusy / renderToolchainStatus / renderFixLLMTelemetry /",
  "// clearFixLLMTelemetry / updateFixCenterAvailability / fixHandleEvent /",
  "// runCompileOnce / runFixOnce / fixRounds / startFixCenter / continueFixCenter +",
  "// 顶层监听器（btn-fix-center / btn-fix-continue / btn-fix-errors /",
  "// btn-fix-rollback + continue 文案——import 时绑定：module 脚本延迟执行，DOM 已就绪）。",
  "// 纯件在 fx/*.js（generate / llm / code）；状态读 A 簇（generate-recommend）",
  "// chosenPlatform / selectedSlugs（活绑定只读——本簇是 toolchains 主写簇）。",
  "// 跨簇：recordLLMUsage（usage）/ reportRecentStatus（recent）/ markStepDone",
  "//（step-state）。A 簇对本簇的服务调用（updateFixCenterAvailability）仍经",
  "// host 启动区注册的 setClusterDeps 闭包（与工单 13 pins 同构——A 不 import",
  "// 本簇，避免 ui→ui 环；本簇单向 import A）。",
  'import { $, apiPost, toast } from "/js/app.js";',
  'import { fmtSeconds, syncCollapseBtn } from "/js/fx/generate.js";',
  'import { parseSSE, formatLLMTelemetry } from "/js/fx/llm.js";',
  'import { maincContentEmpty, maincLineOffsetRange, isMainCPath } from "/js/fx/code.js";',
  'import { chosenPlatform, selectedSlugs } from "/js/ui/generate-recommend.js";',
  'import { reportRecentStatus } from "/js/ui/recent.js";',
  'import { recordLLMUsage } from "/js/ui/usage.js";',
  'import { markStepDone } from "/js/ui/step-state.js";',
  "",
];
const exportTail = [
  "",
  "// ---- 本簇导出面（host / generate-core 顶部 import 活绑定调用点） ----",
  "// 说明（工单 16 记录）：host 实际使用 renderToolchainStatus / setToolchains /",
  "// updateFixCenterAvailability（启动区与 setSettingsDeps 回调用）；generate-core",
  "// 导入 startFixCenter / compileBanner / toolchains（工单 15 的 setGenerateCoreDeps",
  "// 接缝已由静态 import 取代）。runCompileOnce / runFixOnce / fixRounds /",
  "// continueFixCenter / FIX_MAX_ROUNDS / fixLoop 经检查表导出为模块 API",
  "//（fixLoop.resume 结构钉在 tests/test_generate_check_contract.py）。",
  "export { startFixCenter, continueFixCenter, runCompileOnce, runFixOnce, fixRounds,",
  "  renderToolchainStatus, updateFixCenterAvailability, FIX_MAX_ROUNDS, fixLoop,",
  "  toolchains, setToolchains, compileBanner };",
  "",
];
const src = [...header, bodyTxt, ...exportTail].join("\n");
if (src.includes("readinessState")) throw new Error("module must not contain readinessState");
writeFileSync(mod, src, "utf8");
console.log("module written:", mod, "(", src.split("\n").length, "lines )");

// ---- 4) generate-core.js：接缝还原为静态 import ----
let core = readFileSync(coreMod, "utf8");
if (core.includes("setGenerateCoreDeps")) {
  const seamRe = /const coreDeps = \{ startFixCenter: null, compileBanner: null, toolchainsGet: null \};\n\/\/ 修复中心服务（host 注册）：renderGenerateSuccess 的自动编译触发 \/ 无工具链横幅 \/\n\/\/ 工具链可用性读取。工单 16 迁出修复中心后改静态 import。\nfunction setGenerateCoreDeps\(deps\) \{ Object\.assign\(coreDeps, deps\); \}\n\n/;
  if (!seamRe.test(core)) throw new Error("core seam block not found");
  core = core.replace(seamRe, "");
  const seams = [
    ["if ((coreDeps.toolchainsGet ? coreDeps.toolchainsGet() : {})[chosenPlatform]) {",
     "if ((toolchains || {})[chosenPlatform]) {"],
    ["setTimeout(() => coreDeps.startFixCenter(), 100);",
     "setTimeout(() => startFixCenter(), 100);"],
    ['coreDeps.compileBanner("notool", "未检测到工具链，跳过自动编译（可在设置页填 uv4_path / gmake_path）");',
     'compileBanner("notool", "未检测到工具链，跳过自动编译（可在设置页填 uv4_path / gmake_path）");'],
  ];
  for (const [from, to] of seams) {
    const c = core.split(from).length - 1;
    if (c !== 1) throw new Error("core seam count != 1: " + from.slice(0, 50));
    core = core.replace(from, to);
  }
  const importSeam = 'import { refreshRecent } from "/js/ui/recent.js";';
  if (!core.includes(importSeam)) throw new Error("core recent import not found");
  core = core.replace(importSeam,
    importSeam + '\nimport { startFixCenter, compileBanner, toolchains } from "/js/ui/generate-fix.js";  // 修复中心（工单 16 迁出→静态 import，取代工单 15 接缝）');
  core = core.replace(
    "  initScoreChecklist, setGenerateCoreDeps };",
    "  initScoreChecklist };");
  core = core.replace(
    "// 说明（工单 15 记录）：generateMain / renderScoreChecklist /",
    "// 说明（工单 15 记录，工单 16 修订）：generateMain / renderScoreChecklist /");
  core = core.replace(
    "// setGenerateCoreDeps。",
    "// 修复中心服务已随工单 16 改静态 import（startFixCenter / compileBanner / toolchains）。");
  core = core.replace(
    "// 跨簇服务（修复中心，host 内联暂不可静态 import）：startFixCenter /\n// compileBanner / toolchainsGet 经 setGenerateCoreDeps 接缝注册（index.html\n// 启动区；工单 16 迁出修复中心后改静态 import）。",
    "// 跨簇服务（修复中心）静态 import 自 ui/generate-fix.js（工单 16 迁出后由\n// 工单 15 的接缝改为静态 import）；host 侧不再注册。");
  if (core.includes("coreDeps") || core.includes("setGenerateCoreDeps")) throw new Error("core seam residual");
  writeFileSync(coreMod, core, "utf8");
  console.log("core rewired: static import from generate-fix.js");
} else {
  console.log("core already static (skip)");
}

// ---- 5) index.html 手术（顺序：import 行 → 写点改 setter → 注记） ----
{
  const i = must(lines.findIndex((l) => l.includes('from "/js/ui/generate-core.js"')), "generate-core import");
  lines[i] = lines[i].replace(", setGenerateCoreDeps", "");
  if (lines[i].includes("setGenerateCoreDeps")) throw new Error("core import setGenerateCoreDeps residual");
  lines.splice(i + 1, 0,
    'import { renderToolchainStatus, setToolchains, updateFixCenterAvailability } from "/js/ui/generate-fix.js";');
}
{
  const i = must(lines.findIndex((l) => l.includes('setGenerateCoreDeps({ startFixCenter')), "setGenerateCoreDeps registration");
  lines.splice(i, 1);   // 工单 15 接缝已由静态 import 取代
}
{
  const i = must(lines.findIndex((l) => l.includes("toolchains = ts; renderToolchainStatus();")), "applyToolchains callback");
  lines[i] = lines[i].replace("toolchains = ts; renderToolchainStatus();", "setToolchains(ts); renderToolchainStatus();");
  if (lines[i].includes("toolchains = ts")) throw new Error("applyToolchains write residual");
}
{
  const i = must(lines.findIndex((l) => l.includes("toolchains = state.toolchains || { stm32: false, mspm0: false };")), "init toolchains write");
  lines[i] = lines[i].replace("toolchains = state.toolchains || { stm32: false, mspm0: false };",
    "setToolchains(state.toolchains || { stm32: false, mspm0: false });");
  if (lines[i].includes("toolchains = state")) throw new Error("init toolchains write residual");
}
{
  const i = must(lines.findIndex((l) => l.includes("工具链重算（经 setSettingsDeps 接缝写宿主 toolchains +")), "host comment");
  lines[i] = lines[i].replace("写宿主 toolchains", "写 generate-fix 的 toolchains（setToolchains）");
}
{
  const a = must(lines.findIndex((l) => l.startsWith("// 生成页：10. 修复中心（工单 autocompile-loop/01）")), "fix header (re)");
  const da = a - 1;
  if (!lines[da].startsWith("// ------")) throw new Error("dash before fix not found (re)");
  const b = must(lines.findIndex((l) => l.startsWith("// 修订与深化阶段卡（工单 revise-deepen/05）")), "revise header (re)");
  const db = b - 1;
  if (!lines[db].startsWith("// ------")) throw new Error("dash before revise not found (re)");
  const gap = lines.slice(da, db).join(eol);
  if (!gap.includes("async function startFixCenter() {") || !gap.includes("function fixHandleEvent(type, raw, outputDir) {")) throw new Error("re-anchored gap lost cluster?");
  const note = [
    "// ---------------------------------------------------------------------------",
    "// 生成页：10. 修复中心（工单 autocompile-loop/01）——编译修复循环 / 横幅 /",
    "// 结果表 / telemetry / 就绪度",
    "// ---------------------------------------------------------------------------",
    "// 已迁至 static/js/ui/generate-fix.js（阶段 2 工单 16）：FIX_MAX_ROUNDS /",
    "// toolchains（export let + setToolchains——主写簇）/ fixLoop / lastFix* /",
    "// fixSourceCache + 25 函数 + 4 监听器（btn-fix-center / btn-fix-continue /",
    "// btn-fix-errors / btn-fix-rollback）。fmtSeconds 已迁 fx/generate.js（工单 16）。",
    "// host 经顶部 import 调用 renderToolchainStatus / setToolchains /",
    "// updateFixCenterAvailability（启动区与 setSettingsDeps 回调）；generate-core",
    "// 静态 import startFixCenter / compileBanner / toolchains（取代工单 15 的",
    "// 修复中心接缝）。读写迁移组：A 簇仍经 setClusterDeps 闭包调用",
    "// updateFixCenterAvailability（与工单 13 pins 同构）。",
    "",
  ];
  lines.splice(da, db - da, ...note);
}

// ---- 6) 校验 ----
const out = lines.join(eol);
if ((out.match(/from "\/js\/ui\/generate-fix\.js"/) || []).length !== 1) throw new Error("generate-fix import count != 1");
for (const n of ["FIX_MAX_ROUNDS", "startFixCenter", "continueFixCenter", "runCompileOnce",
  "runFixOnce", "fixRounds", "compileBanner", "renderToolchainStatus",
  "updateFixCenterAvailability", "fixHandleEvent", "fixLoop", "toolchains", "fmtSeconds"]) {
  if (n === "FIX_MAX_ROUNDS" || n === "toolchains" || n === "fixLoop" || n === "fmtSeconds") {
    if (new RegExp("(const|let)\\s+" + n + "\\b").test(out)) throw new Error("residual " + n);
  } else if (new RegExp("function\\s+\\w*\\s*" + n + "\\(").test(out)) {
    throw new Error("residual definition of " + n);
  }
}
if (out.includes('$("btn-fix-center").addEventListener')) throw new Error("btn-fix-center listener should have moved");
if (!out.includes("setToolchains(state.toolchains || { stm32: false, mspm0: false });")) throw new Error("init setToolchains call lost");
if (!out.includes("updateFixCenterAvailability: () => updateFixCenterAvailability(),")) throw new Error("clusterDeps registration lost");
if (out.includes("setGenerateCoreDeps")) throw new Error("setGenerateCoreDeps residual in index.html");
if (!out.includes('import { renderToolchainStatus, setToolchains, updateFixCenterAvailability } from "/js/ui/generate-fix.js";')) throw new Error("host fix import missing");

writeFileSync(p, out, "utf8");
console.log("OK: fix center moved to ui/generate-fix.js; host rewired; lines now", lines.length);

// ---- 7) generate-recommend.js 头部注释更新 ----
{
  const aPath = "src/contest_generator/static/js/ui/generate-recommend.js";
  let aTxt = readFileSync(aPath, "utf8");
  const before = aTxt;
  aTxt = aTxt.replace(
    "//   （修复\n//   中心——工单 16 迁）/",
    "//   （修复\n//   中心——已随工单 16 迁 ui/generate-fix.js，经 host 注册闭包）/");
  if (aTxt === before) {
    // 换一种精确匹配（真实换行形态，CRLF 容错）
    const alt = /updateFixCenterAvailability（修复\r?\n\/\/   中心——工单 16 迁）/;
    if (!alt.test(aTxt)) throw new Error("A-cluster header note not updated");
    aTxt = aTxt.replace(alt,
      "updateFixCenterAvailability（修复\n//   中心——已随工单 16 迁 ui/generate-fix.js，经 host 注册闭包）");
  }
  writeFileSync(aPath, aTxt, "utf8");
  console.log("A-cluster header note updated");
}
