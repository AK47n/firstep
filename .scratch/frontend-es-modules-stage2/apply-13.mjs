// 阶段 2 工单 13：引脚-多实例簇（B）迁 static/js/ui/generate-pins.js。
// ① 提取 index.html 2313-3204（6.5 多实例配置 + 7 引脚配置两节，含两条
//    "已迁至 fx" 历史注记）→ 逐字搬入新模块（状态/常量行加 export 前缀，
//    instances/instancePinTarget 前置声明，4 个接缝函数 + 导出清单在脚本内拼装）；
// ② index.html：host 顶部 import 行 + 实例状态声明删除（A 注记改口）+
//    簇体→注记 + setClusterDeps 注册改挂本簇导出（7 项薄胶水删、注释改口）。
// 全程 CRLF 感知；模块文件 LF（与既有 ui/*.js 一致）。
import { readFileSync, writeFileSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
const mod = "src/contest_generator/static/js/ui/generate-pins.js";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };
if (lines.some((l) => l.includes('from "/js/ui/generate-pins.js"'))) throw new Error("import already present");

const FUNCS = ["instList", "renderInstanceConfig", "instanceBlock", "instanceRow", "addInstance",
  "delInstance", "pickInstancePin", "clearInstancePin", "assignInstancePin", "pinIndex",
  "pinRoles", "moduleColorMap", "overviewRolesAt", "overviewRing", "overviewPie", "pinSupports",
  "roleInstances", "pinIsTypeLevel", "pwmRoleChannel", "mspm0PwmAllowed", "pinCanHost",
  "pinListsType", "pinMissReason", "pinMacroFamilies", "pinHint", "renderPinCard", "loadPinBoard",
  "renderPinLegend", "renderPinOverviewLegend", "renderPinBoard", "svgPin", "renderPinRoles",
  "unbindRole", "bindRole", "showPinMenu"];

// ---- 1) 定位并提取簇体（6.5 双横线头 → main.c 双横线头，不含后者） ----
const h65 = must(lines.findIndex((l) => l.startsWith("// 生成页：6.5 多实例配置")), "6.5 header");
const dash65 = h65 - 1;
if (!lines[dash65].startsWith("// ------")) throw new Error("dash before 6.5 not found");
const hmc = must(lines.findIndex((l) => l.startsWith("// main.c 行号 + 语法着色")), "main.c header");
const dashMc = hmc - 1;
if (!lines[dashMc].startsWith("// ------")) throw new Error("dash before main.c not found");
let body = lines.slice(dash65, dashMc);   // 2313..3204（含末尾空行）
const bodyTxt = body.join(eol);
for (const n of FUNCS) {
  if (!new RegExp("function\\s+" + n + "\\(").test(bodyTxt)) throw new Error("missing function " + n);
}
for (const frag of ['$("btn-pin-reset").addEventListener', '$("btn-pin-rotate").addEventListener',
  '$("btn-pin-overview").addEventListener', '$("btn-pin-auto").addEventListener',
  'document.addEventListener("keydown"', 'const LED_COLORS', 'const PIN_TYPE_STYLE', 'const PIN_TYPE_ZH',
  'const MODULE_COLORS', 'let pinBoard = null;', 'let pinBindings = {};', 'let pinOverview = false;']) {
  if (!bodyTxt.includes(frag)) throw new Error("body missing frag: " + frag.slice(0, 40));
}
// 状态/常量行加 export 前缀（逐字搬移 + export 标注；每行精确命中一次）
let stateHits = 0;
const stateRx = [
  [/^const LED_COLORS = /, "export const LED_COLORS = ", "LED_COLORS"],
  [/^let pinBoard = null;/, "export let pinBoard = null;", "pinBoard"],
  [/^let pinBoardError = "";/, 'export let pinBoardError = "";', "pinBoardError"],
  [/^let pinBindings = \{\};/, "export let pinBindings = {};", "pinBindings"],
  [/^let pinUnbound = new Set\(\);/, "export let pinUnbound = new Set();", "pinUnbound"],
  [/^let pinShowOptional = false;/, "export let pinShowOptional = false;", "pinShowOptional"],
  [/^let pinHighlight = null;/, "export let pinHighlight = null;", "pinHighlight"],
  [/^let pinRotation = 0;/, "export let pinRotation = 0;", "pinRotation"],
  [/^let pinOverview = false;/, "export let pinOverview = false;", "pinOverview"],
  [/^const PIN_TYPE_STYLE = \{/, "export const PIN_TYPE_STYLE = {", "PIN_TYPE_STYLE"],
  [/^const PIN_TYPE_ZH = \{/, "export const PIN_TYPE_ZH = {", "PIN_TYPE_ZH"],
  [/^const MODULE_COLORS = \[/, "export const MODULE_COLORS = [", "MODULE_COLORS"],
];
body = body.map((l) => {
  for (const [re, to] of stateRx) {
    if (re.test(l)) { stateHits++; return l.replace(re, to); }
  }
  return l;
});
if (stateHits !== stateRx.length) throw new Error("state export lines expected " + stateRx.length + ", got " + stateHits);

// ---- 2) 拼装 ui/generate-pins.js（LF；头部注释 + imports + 状态 + 簇体 + 接缝函数 + 导出） ----
const header = [
  "// ui/generate-pins.js — 生成页 · 实例配置 + 引脚板图（阶段 2 工单 13，源自",
  "// index.html 2313-3204 两节：6.5 多实例配置 + 7 引脚配置）",
  "//",
  "// DOM 胶水全量迁入：实例增删 / 显示名 / 颜色 / 板图选脚（instList /",
  "// renderInstanceConfig / instanceBlock / instanceRow / addInstance / delInstance /",
  "// pickInstancePin / clearInstancePin / assignInstancePin）+ 引脚板图（renderPinCard /",
  "// loadPinBoard / renderPinLegend / renderPinOverviewLegend / renderPinBoard / svgPin /",
  "// renderPinRoles / unbindRole / bindRole / showPinMenu）+ 总览着色 / 能力判定 / 自动配置。",
  "// 纯件在 fx/*.js（module.js：multiInstanceModules / instancePayload /",
  "// ensureDefaultInstances；generate.js：collectBindings；core.js：esc）。",
  "// 状态所有权（本模块 = 主写簇；host 经顶部 import 活绑定只读，写经导出函数）：",
  "//   instances / instancePinTarget / pinBoard / pinBoardError / pinBindings /",
  "//   pinUnbound / pinShowOptional / pinHighlight / pinRotation / pinOverview +",
  "//   常量 LED_COLORS / PIN_TYPE_STYLE / PIN_TYPE_ZH / MODULE_COLORS。",
  "// host → 本簇：顶部 import 代理（instances / pinBindings / pinUnbound / pinRoles /",
  "//   renderInstanceConfig / renderPinCard / loadPinBoard——generateMain /",
  "//   renderGenerateSuccess / btn-generate / handoffPinLines 读点与启动占位渲染）",
  "//   与 setClusterDeps 注册改挂本簇导出（renderPinCard / renderInstanceConfig /",
  "//   loadPinBoard / resetPinState / resetInstances / clearInstanceTarget /",
  "//   backfillInstances——推荐簇 A 的跨簇服务入口：工单 12 的 host 薄胶水接缝 →",
  "//   本票迁入本体，见 index.html 启动区）。",
  "// 顶层 addEventListener（Esc 取消选脚 / btn-pin-reset / btn-pin-rotate /",
  "// btn-pin-overview / btn-pin-auto）在 import 时绑定（module 脚本延迟执行，DOM 已就绪）。",
  'import { $, apiGet, apiPost } from "/js/app.js";',
  'import { esc } from "/js/fx/core.js";',
  'import { multiInstanceModules, ensureDefaultInstances } from "/js/fx/module.js";',
  'import { collectBindings } from "/js/fx/generate.js";',
  'import { syncStep7 } from "/js/ui/step-state.js";',
  'import { chosenPlatform, expanded, selectedSlugs } from "/js/ui/generate-recommend.js";',
  "",
  "// ---- 全局状态：多实例 + 引脚板图（随簇；host 经 import 活绑定读） ----",
  "export let instances = {};               // 多实例配置（工单 04）：{ slug: [{name, variant, pin}] }",
  "export let instancePinTarget = null;     // 正在从板图选引脚的实例 { slug, index }（null = 非选脚模式）",
  "",
];
const seam = [
  "// ---- 跨簇接缝函数（原 index.html 启动区 setClusterDeps 薄胶水迁入本体；工单 12",
  "// 接缝 → 13 静态化；推荐簇 A 经 setClusterDeps 注册调用） ----",
  "export function resetPinState() {",
  '  pinBindings = {}; pinUnbound = new Set(); pinHighlight = null; pinHint("");',
  "}",
  "export function resetInstances() {",
  "  instances = {}; instancePinTarget = null; renderInstanceConfig();",
  "}",
  "export function clearInstanceTarget() {",
  "  instancePinTarget = null;",
  "}",
  "export function backfillInstances(dataInstances) {",
  "  for (const slug of Object.keys(dataInstances)) {",
  "    instances[slug] = (dataInstances[slug] || []).map((i) => ({",
  '      name: String(i.name || ""), variant: i.variant || "", pin: i.pin || "",',
  "    }));",
  "  }",
  "  instancePinTarget = null;  // 旧选脚目标可能越界，清掉防陈旧高亮",
  "}",
  "",
  "// ---- 本簇导出面（host 顶部 import 代理 + 推荐簇 A 接缝导点名） ----",
  "export { renderInstanceConfig, renderPinCard, loadPinBoard, bindRole, unbindRole, assignInstancePin, addInstance, delInstance, pinRoles };",
  "",
];
writeFileSync(mod, [...header, ...body, "", ...seam].join("\n"), "utf8");
console.log("module written:", mod);

// ---- 3) index.html：host import 行（step-state import 之后） ----
{
  const i = must(lines.findIndex((l) => l.includes('from "/js/ui/step-state.js"')), "step-state import");
  lines.splice(i + 1, 0,
    'import { instances, pinBindings, pinUnbound, pinRoles, renderInstanceConfig, renderPinCard, loadPinBoard, resetPinState, resetInstances, clearInstanceTarget, backfillInstances } from "/js/ui/generate-pins.js";');
}

// ---- 4) 全局状态段：实例两行删除 + A 注记改口 ----
{
  const i = must(lines.findIndex((l) => l.includes("instances / instancePinTarget 属引脚-多实例簇")), "A note");
  if (!lines[i + 1].includes("工单 13 迁），留 host。")) throw new Error("A note next line mismatch");
  if (!/^let instances = \{\}/.test(lines[i + 2])) throw new Error("instances decl lost?");
  if (!/^let instancePinTarget = null;/.test(lines[i + 3])) throw new Error("instancePinTarget decl lost?");
  lines.splice(i, 4,
    "// setRecommendClarifications）。instances / instancePinTarget 属引脚-多实例簇，",
    "// 已随工单 13 迁至 static/js/ui/generate-pins.js（host 经 import 活绑定读、经导出函数写）。");
}

// ---- 5) 簇体 → 注记（重新定位：3/4 步已移动数组下标） ----
{
  const a = must(lines.findIndex((l) => l.startsWith("// 生成页：6.5 多实例配置")), "6.5 header");
  const da = a - 1;
  if (!lines[da].startsWith("// ------")) throw new Error("dash before 6.5 not found (re)");
  const b = must(lines.findIndex((l) => l.startsWith("// main.c 行号 + 语法着色")), "main.c header");
  const db = b - 1;
  if (!lines[db].startsWith("// ------")) throw new Error("dash before main.c not found (re)");
  const gap = lines.slice(da, db).join(eol);
  if (!gap.includes("const LED_COLORS") || !gap.includes("function showPinMenu(")) throw new Error("re-anchored gap lost cluster?");
  const note = [
    "// ---------------------------------------------------------------------------",
    "// 生成页：6.5 多实例配置 + 7. 引脚配置（引脚-多实例簇 B）",
    "// ---------------------------------------------------------------------------",
    "// 已迁至 static/js/ui/generate-pins.js（阶段 2 工单 13）：实例增删 / 显示名 /",
    "// 颜色 / 板图选脚 / 引脚板图 SVG / 角色清单与锚定菜单 / 总览着色 / 自动配置",
    "// （instList / renderInstanceConfig / renderPinCard / loadPinBoard /",
    "// renderPinBoard / svgPin / renderPinRoles / bindRole / unbindRole /",
    "// showPinMenu 等，共 35 函数 + 4 接缝函数）。状态随簇（instances /",
    "// instancePinTarget / pinBoard / pinBindings / pinUnbound / pinHighlight /",
    "// pinRotation / pinOverview 等——host 经顶部 import 活绑定读；写经导出函数",
    "// resetPinState / resetInstances / clearInstanceTarget / backfillInstances，",
    "// 推荐簇 A 的跨簇服务经 setClusterDeps 注册调用，见启动区）。",
    "",
  ];
  lines.splice(da, db - da, ...note);
}

// ---- 6) setClusterDeps 注册：引脚-多实例 7 项薄胶水 → 本簇导出静态引用 ----
{
  const i = must(lines.findIndex((l) => l.startsWith("  resetPinState: () => { pinBindings = {}")), "glue resetPinState");
  const j = must(lines.findIndex((l) => l === "    instancePinTarget = null;  // 旧选脚目标可能越界，清掉防陈旧高亮"), "glue backfill tail");
  if (!/^  \},$/.test(lines[j + 1])) throw new Error("glue backfill close mismatch");
  lines.splice(i, j + 2 - i,
    "  resetPinState,",
    "  resetInstances,",
    "  clearInstanceTarget,",
    "  renderPinCard,",
    "  renderInstanceConfig,",
    "  loadPinBoard,",
    "  backfillInstances,");
  const c = must(lines.findIndex((l) => l.includes("backfillInstances——工单 13 迁出后改静态 import）")), "seam comment");
  lines[c] = lines[c].replace("backfillInstances——工单 13 迁出后改静态 import）", "backfillInstances——工单 13 已迁 ui/generate-pins.js，注册改挂静态 import）");
}

// ---- 7) 校验 ----
const out = lines.join(eol);
if ((out.match(/from "\/js\/ui\/generate-pins\.js"/) || []).length !== 1) throw new Error("pins import count != 1");
for (const n of FUNCS) {
  if (new RegExp("function\\s+" + n + "\\(").test(out)) throw new Error("residual definition of " + n);
}
if (/(^|\r?\n)let (instances|instancePinTarget|pinBoard|pinBoardError|pinBindings|pinUnbound|pinShowOptional|pinHighlight|pinRotation|pinOverview)\s*=/m.test(out)) throw new Error("residual B state decl");
if (/(^|\r?\n)const (LED_COLORS|PIN_TYPE_STYLE|PIN_TYPE_ZH|MODULE_COLORS)\b/m.test(out)) throw new Error("residual B const");
for (let i = 0; i < lines.length; i++) {
  const l = lines[i];
  if (l.trim().startsWith("//")) continue;
  if (/(^|[;{][\s]*)(pinBindings|instances|instancePinTarget|pinBoard|pinBoardError|pinShowOptional|pinHighlight|pinRotation|pinOverview|pinUnbound)\s*=(?!=)/.test(l)) {
    throw new Error("residual B state assignment -> line " + (i + 1) + ": " + l.trim());
  }
}
if (!out.includes("  resetPinState,\r\n  resetInstances,")) throw new Error("setClusterDeps shorthand missing");
if (!out.includes("renderPinCard();  // 引脚配置卡（工单 03）：初始占位文案")) throw new Error("startup renderPinCard call lost");
if (!out.includes("pinRoles()")) throw new Error("host pinRoles read lost");
if (!out.includes("handoffPinLines")) throw new Error("handoffPinLines lost");

writeFileSync(p, out, "utf8");
console.log("OK: pins cluster moved to ui/generate-pins.js; host rewired; lines now", lines.length);
