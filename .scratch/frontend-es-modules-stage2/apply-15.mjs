// 阶段 2 工单 15：生成页「生成执行 + 评分清单 + 交付 Handoff」簇迁
// static/js/ui/generate-core.js。
// ① 提取 index.html 两段：A = 生成页：8/9 节（2335-2443：SKELETON_MODES +
//    generateMain + 骨架/冒烟监听器 + renderGenerateSuccess +
//    desktopTopicOutputEnabled + 桌面输出/选目录监听器）；B = 生成页：11 节
//    （2563-2854：renderArtifacts + 评分清单 5 函数 + handoff* 6 函数 + 交接/
//    复制监听器）→ 逐字搬入新模块（头部注释 + imports + 接缝 + 导出清单在脚本
//    内拼装；renderGenerateSuccess 内 3 处修复中心调用改走接缝）。
// ② index.html：host 顶部 import 行（generate-mainc import 之后）+ A 簇 import
//    补 currentTopicId + 启动区 setGenerateCoreDeps 接缝 + 两段簇体→注记。
// ③ 留 host：btn-generate 覆盖重发监听器（依赖 host 内联 readinessState）。
// 全程 CRLF 感知；模块文件 LF（与既有 ui/*.js 一致）。
import { readFileSync, writeFileSync, existsSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
const mod = "src/contest_generator/static/js/ui/generate-core.js";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };
if (lines.some((l) => l.includes('from "/js/ui/generate-core.js"'))) throw new Error("import already present");
if (existsSync(mod)) throw new Error("module file already exists: " + mod);

// ---- 1) 定位并提取簇体 A（生成页：8. main.c 骨架 → collectBindings 注记，不含后者） ----
const h8 = must(lines.findIndex((l) => l.startsWith("// 生成页：8. main.c 骨架")), "8 header");
const dashA = h8 - 1;
if (!lines[dashA].startsWith("// ------")) throw new Error("dash before 8 header not found");
const cb = must(lines.findIndex((l) => l.startsWith("// 已迁至 static/js/fx/generate.js（工单 08）：collectBindings。")), "collectBindings note");
const bodyA = lines.slice(dashA, cb);
// ---- 2) 定位并提取簇体 B（生成页：11. 交接提示词 → 生成页：10. 修复中心双横线，不含后者） ----
const h11 = must(lines.findIndex((l) => l.startsWith("// 生成页：11. 交接提示词（Handoff）")), "11 header");
const dashB = h11 - 1;
if (!lines[dashB].startsWith("// ------")) throw new Error("dash before 11 header not found");
const h10 = must(lines.findIndex((l) => l.startsWith("// 生成页：10. 修复中心（工单 autocompile-loop/01）")), "10 header");
const dashC = h10 - 1;
if (!lines[dashC].startsWith("// ------")) throw new Error("dash before 10 header not found");
const bodyB = lines.slice(dashB, dashC);

const fnA = ["generateMain", "renderGenerateSuccess", "desktopTopicOutputEnabled"];
const fnB = ["renderArtifacts", "renderScoreChecklist", "scoreChecklistIdsNow",
  "scoreChecklistSyncCurrent", "scoreChecklistExportNow", "initScoreChecklist",
  "handoffPlatformLabel", "handoffPlatformIde", "handoffModuleLines",
  "handoffWarnings", "handoffPinLines", "handoffReferenceLines"];
const names = ["SKELETON_MODES", ...fnA, ...fnB];
for (const n of fnA) {
  if (!new RegExp("function\\s+\\w*\\s*" + n + "\\(").test(bodyA.join(eol))) throw new Error("bodyA missing " + n);
}
for (const n of fnB) {
  if (!new RegExp("function\\s+\\w*\\s*" + n + "\\(").test(bodyB.join(eol))) throw new Error("bodyB missing " + n);
}
if (!bodyA.join(eol).includes("const SKELETON_MODES = {")) throw new Error("bodyA missing SKELETON_MODES");
if (bodyA.join(eol).includes("btn-generate")) throw new Error("bodyA must not contain btn-generate");
if (bodyB.join(eol).includes("btn-generate")) throw new Error("bodyB must not contain btn-generate");
if (bodyB.join(eol).includes("readinessState")) throw new Error("bodyB must not contain readinessState");
for (const frag of ['$("btn-skeleton").addEventListener("click", () => generateMain("skeleton"));',
  '$("btn-smoke").addEventListener("click", () => generateMain("smoke"));',
  '$("desktop-topic-output").addEventListener("change", () => {',
  '$("btn-pick-output-dir").addEventListener("click", async () => {',
  '$("btn-handoff").addEventListener("click", async () => {',
  '$("btn-handoff-copy").addEventListener("click", async () => {',
  '$("btn-copy-dir").addEventListener("click", async () => {']) {
  const hit = bodyA.join(eol).includes(frag) || bodyB.join(eol).includes(frag);
  if (!hit) throw new Error("cluster missing listener: " + frag.slice(0, 50));
}

// ---- 3) 拼装 ui/generate-core.js（LF；头部注释 + imports + 接缝 + 簇体 A/B + 导出） ----
const header = [
  "// ui/generate-core.js — 生成页 · 生成执行 + 评分清单 + 交付 Handoff",
  "//（阶段 2 工单 15，源自 index.html 生成页 8/9/11 三节）。",
  "//",
  "// DOM 胶水全量迁入：SKELETON_MODES + generateMain（骨架/自检冒烟共用） /",
  "// renderGenerateSuccess（成功区：目录/包含路径/模块/评分清单/产物树/自动编译） /",
  "// desktopTopicOutputEnabled（桌面输出开关） / renderArtifacts（自动附带产物） /",
  "// 评分清单 5 函数（renderScoreChecklist / scoreChecklistIdsNow /",
  "// scoreChecklistSyncCurrent / scoreChecklistExportNow / initScoreChecklist） /",
  "// 交接 6 函数（handoffPlatformLabel / handoffPlatformIde / handoffModuleLines /",
  "// handoffWarnings / handoffPinLines / handoffReferenceLines）+ 顶层监听器",
  "//（btn-skeleton / btn-smoke / desktop-topic-output change / btn-pick-output-dir /",
  "// btn-handoff / btn-handoff-copy / btn-copy-dir——import 时绑定：module 脚本",
  "// 延迟执行，DOM 已就绪，同 generate-recommend 先例）。纯件在 fx/*.js",
  "//（generate / module / score / draft，本模块 import 调用）。",
  "// 状态读（只读，写经各 setter）：A 簇 generate-recommend 的 chosenPlatform /",
  "// selectedSlugs / expanded / warnings / scorePoints / selectedReferenceIds /",
  "// autoReferenceIds / currentTopicId（工单 15 起 export let——读取方 import）；",
  "// B 簇 generate-pins 的 instances / pinBindings / pinUnbound / pinRoles()。",
  "// 跨域调用：syncStep7（fx/draft）/ markStepDone（step-state）/",
  "// syncMainCHighlight（generate-mainc）/ refreshRecent（recent）。",
  "// 跨簇服务（修复中心，host 内联暂不可静态 import）：startFixCenter /",
  "// compileBanner / toolchainsGet 经 setGenerateCoreDeps 接缝注册（index.html",
  "// 启动区；工单 16 迁出修复中心后改静态 import）。",
  "// 留 host：btn-generate 覆盖重发监听器（依赖 host 内联 readinessState 前置",
  "// 校验；经顶部 import 调用本模块 renderGenerateSuccess）。",
  'import { $, apiGet, apiPost, state, KIND_TEXT, toast } from "/js/app.js";',
  'import { formatResModules } from "/js/fx/generate.js";',
  'import { instancePayload } from "/js/fx/module.js";',
  'import { scoreChecklistId, scoreChecklistKey, scoreChecklistLoad, scoreChecklistItemsHTML, scoreChecklistProgressHTML, scoreChecklistSave, scoreChecklistExportText, formatScorePoints } from "/js/fx/score.js";',
  'import { syncStep7 } from "/js/fx/draft.js";',
  'import { chosenPlatform, selectedSlugs, expanded, warnings, scorePoints, selectedReferenceIds, autoReferenceIds, currentTopicId } from "/js/ui/generate-recommend.js";',
  'import { instances, pinBindings, pinUnbound, pinRoles } from "/js/ui/generate-pins.js";',
  'import { markStepDone } from "/js/ui/step-state.js";',
  'import { syncMainCHighlight } from "/js/ui/generate-mainc.js";',
  'import { refreshRecent } from "/js/ui/recent.js";',
  "",
  "const coreDeps = { startFixCenter: null, compileBanner: null, toolchainsGet: null };",
  "// 修复中心服务（host 注册）：renderGenerateSuccess 的自动编译触发 / 无工具链横幅 /",
  "// 工具链可用性读取。工单 16 迁出修复中心后改静态 import。",
  "export function setGenerateCoreDeps(deps) { Object.assign(coreDeps, deps); }",
  "",
];
const between = [
  "// ---------------------------------------------------------------------------",
  "// （btn-generate 覆盖重发监听器与其 readiness 前置校验留 index.html——依赖",
  "// host 内联 readinessState；renderGenerateSuccess 经 host 顶部 import 调用）",
  "// ---------------------------------------------------------------------------",
  "",
];
const exportTail = [
  "",
  "// ---- 本簇导出面（host 顶部 import 活绑定调用点） ----",
  "// 说明（工单 15 记录）：generateMain / renderScoreChecklist /",
  "// scoreChecklistSyncCurrent / scoreChecklistExportNow 当前无 host 调用点",
  "//（监听器随簇迁入），按检查表导出为模块 API；host 实际使用",
  "// renderGenerateSuccess / desktopTopicOutputEnabled / initScoreChecklist /",
  "// setGenerateCoreDeps。",
  "export { generateMain, renderGenerateSuccess, desktopTopicOutputEnabled,",
  "  renderScoreChecklist, scoreChecklistSyncCurrent, scoreChecklistExportNow,",
  "  initScoreChecklist, setGenerateCoreDeps };",
  "",
];

// ---- 4) renderGenerateSuccess 内 3 处修复中心调用 → 接缝（逐字特判） ----
let bodyA2 = bodyA.join("\n");
const seams = [
  ["if ((toolchains || {})[chosenPlatform]) {",
   "if ((coreDeps.toolchainsGet ? coreDeps.toolchainsGet() : {})[chosenPlatform]) {"],
  ["setTimeout(() => startFixCenter(), 100);",
   "setTimeout(() => coreDeps.startFixCenter(), 100);"],
  ['compileBanner("notool", "未检测到工具链，跳过自动编译（可在设置页填 uv4_path / gmake_path）");',
   'coreDeps.compileBanner("notool", "未检测到工具链，跳过自动编译（可在设置页填 uv4_path / gmake_path）");'],
];
for (const [from, to] of seams) {
  const before = bodyA2.split(from).length - 1;
  if (before !== 1) throw new Error("seam pattern count != 1: " + from.slice(0, 50));
  bodyA2 = bodyA2.replace(from, to);
}
const src = [...header, bodyA2, "", ...between, bodyB.join("\n"), ...exportTail].join("\n");
if (src.includes("readinessState(")) throw new Error("module must not contain readinessState call");
if (src.includes('$("btn-generate")')) throw new Error("module must not contain btn-generate listener");
if (src.includes("function compileBanner")) throw new Error("module must not redefine compileBanner");
if (/const\s+SKELETON_MODES/.test(src) === false) throw new Error("SKELETON_MODES lost");
writeFileSync(mod, src, "utf8");
console.log("module written:", mod, "(", src.split("\n").length, "lines )");

// ---- 5) index.html：host import 行（generate-mainc import 之后）+ A 簇补 currentTopicId ----
{
  const i = must(lines.findIndex((l) => l.includes('from "/js/ui/generate-mainc.js"')), "generate-mainc import");
  lines.splice(i + 1, 0,
    'import { generateMain, renderGenerateSuccess, desktopTopicOutputEnabled, renderScoreChecklist, scoreChecklistSyncCurrent, scoreChecklistExportNow, initScoreChecklist, setGenerateCoreDeps } from "/js/ui/generate-core.js";');
}
{
  const i = must(lines.findIndex((l) => l.includes("lastRecommend, selectedReferenceIds, autoReferenceIds, pythonTemplates")), "A-cluster import");
  lines[i] = lines[i].replace("lastRecommend, selectedReferenceIds,", "lastRecommend, currentTopicId, selectedReferenceIds,");
  if (!lines[i].includes("currentTopicId")) throw new Error("currentTopicId not added to A import");
}

// ---- 6) 启动区：setGenerateCoreDeps 接缝（setSettingsDeps 之后） ----
{
  const i = must(lines.findIndex((l) => l.includes('setSettingsDeps({ applyToolchains:')), "setSettingsDeps call");
  lines.splice(i + 1, 0,
    "setGenerateCoreDeps({ startFixCenter, compileBanner, toolchainsGet: () => toolchains });  // 修复中心服务接缝（工单 16 迁出后改静态 import）");
}

// ---- 7) 两段簇体 → 注记（重新定位：前面 splice 已移动数组下标） ----
{
  const a = must(lines.findIndex((l) => l.startsWith("// 生成页：8. main.c 骨架")), "8 header (re)");
  const da = a - 1;
  if (!lines[da].startsWith("// ------")) throw new Error("dash before 8 not found (re)");
  const aEnd = must(lines.findIndex((l) => l.startsWith("// 已迁至 static/js/fx/generate.js（工单 08）：collectBindings。")), "collectBindings note (re)");
  const gapA = lines.slice(da, aEnd).join(eol);
  if (!gapA.includes("async function generateMain(mode) {") || !gapA.includes("function renderGenerateSuccess(data) {")) throw new Error("re-anchored gapA lost cluster?");
  const noteA = [
    "// ---------------------------------------------------------------------------",
    "// 生成页：8. main.c 骨架 / 自检冒烟 + 生成页：9. 输出目录并生成（成功区 / 桌面输出开关）",
    "// ---------------------------------------------------------------------------",
    "// 已迁至 static/js/ui/generate-core.js（阶段 2 工单 15）：SKELETON_MODES +",
    "// generateMain / renderGenerateSuccess / desktopTopicOutputEnabled + 骨架与",
    "// 冒烟按钮 / 桌面输出开关 / 选目录监听器。host 经顶部 import 调用",
    "// renderGenerateSuccess（btn-generate 覆盖重发监听器）与",
    "// desktopTopicOutputEnabled（readiness 检查）。btn-generate 监听器留 host。",
    "",
  ];
  lines.splice(da, aEnd - da, ...noteA);
}
{
  const b = must(lines.findIndex((l) => l.startsWith("// 生成页：11. 交接提示词（Handoff）")), "11 header (re)");
  const db = b - 1;
  if (!lines[db].startsWith("// ------")) throw new Error("dash before 11 not found (re)");
  const bEnd = must(lines.findIndex((l) => l.startsWith("// 生成页：10. 修复中心（工单 autocompile-loop/01）")), "10 header (re)");
  const dEnd = bEnd - 1;
  if (!lines[dEnd].startsWith("// ------")) throw new Error("dash before 10 not found (re)");
  const gapB = lines.slice(db, dEnd).join(eol);
  if (!gapB.includes("function renderArtifacts(structure, outputDir) {") || !gapB.includes("function initScoreChecklist() {")) throw new Error("re-anchored gapB lost cluster?");
  const noteB = [
    "// ---------------------------------------------------------------------------",
    "// 生成页：11. 交接提示词（Handoff）+ 自动附带产物 / 评分点核对清单",
    "// ---------------------------------------------------------------------------",
    "// 已迁至 static/js/ui/generate-core.js（阶段 2 工单 15）：renderArtifacts /",
    "// renderScoreChecklist / scoreChecklistIdsNow / scoreChecklistSyncCurrent /",
    "// scoreChecklistExportNow / initScoreChecklist / handoffPlatformLabel /",
    "// handoffPlatformIde / handoffModuleLines / handoffWarnings / handoffPinLines /",
    "// handoffReferenceLines + 交接 / 复制路径 / 复制核对表监听器（import 时绑定）。",
    "// host 启动区只调 initScoreChecklist()。",
    "",
  ];
  lines.splice(db, dEnd - db, ...noteB);
}

// ---- 8) 校验 ----
const out = lines.join(eol);
if ((out.match(/from "\/js\/ui\/generate-core\.js"/) || []).length !== 1) throw new Error("generate-core import count != 1");
for (const n of names) {
  if (n === "SKELETON_MODES") {
    if (new RegExp("const\\s+SKELETON_MODES\\b").test(out)) throw new Error("residual const SKELETON_MODES");
  } else {
    if (new RegExp("function\\s+\\w*\\s*" + n + "\\(").test(out)) throw new Error("residual definition of " + n);
  }
}
if (!out.includes('$("btn-generate").addEventListener("click", async () => {')) throw new Error("btn-generate listener lost");
if (out.includes('$("btn-handoff").addEventListener')) throw new Error("btn-handoff listener should have moved");
if (!out.includes("initScoreChecklist();  // 评分点核对清单：勾选持久化 + 复制核对表（事件委托）")) throw new Error("startup initScoreChecklist call lost");
if ((out.match(/desktopTopicOutputEnabled\(\)/g) || []).length < 2) throw new Error("readiness desktopTopicOutputEnabled calls lost");
if (!out.includes("lastRecommend, currentTopicId, selectedReferenceIds,")) throw new Error("host A import currentTopicId missing");
if (!out.includes("setGenerateCoreDeps({ startFixCenter, compileBanner, toolchainsGet: () => toolchains });")) throw new Error("setGenerateCoreDeps registration missing");
if (!out.includes('setGenerateCoreDeps } from "/js/ui/generate-core.js"')) throw new Error("host generate-core import missing");

writeFileSync(p, out, "utf8");
console.log("OK: generate core moved to ui/generate-core.js; host rewired; lines now", lines.length);
