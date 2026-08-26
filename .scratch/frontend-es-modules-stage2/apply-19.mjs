// 阶段 2 工单 19（generatae 八簇收尾）：就绪检查簇迁 static/js/ui/generate-readiness.js。
// ① 提取 index.html 2626-2686（检查能否生成 section 注释 + readinessState /
//    renderReadinessPanel / refreshReadinessPanel / initReadinessCheck）→ 拼装新模块；
// ② index.html：簇体→注记 + host import 行（generate-steps 之后）+ setStepsDeps
//    注册行删除（工单 18 接缝由静态 import 取代——本票正是衔接点）；
// ③ ui/generate-steps.js：stepsDeps/setStepsDeps 删除 + refreshGenOverview 改
//    直接调用 readinessState（静态 import 自 ui/generate-readiness.js）+ 导出面更新。
// 注：stepDoneSet / stepCard 真身在 ui/step-state.js（工单 12 拥有）——issue
// 所述「import 自 ui/generate-steps.js」不实，按 grep 复核（steps ↔ readiness
// 无环：readiness → step-state/A/core；steps → readiness —— readiness 不 import steps）。
// 全程 CRLF 感知；模块文件 LF。
import { readFileSync, writeFileSync, existsSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
const mod = "src/contest_generator/static/js/ui/generate-readiness.js";
const stepsMod = "src/contest_generator/static/js/ui/generate-steps.js";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };
if (lines.some((l) => l.includes('from "/js/ui/generate-readiness.js"'))) throw new Error("import already present");
if (existsSync(mod)) throw new Error("module file already exists: " + mod);

// ---- 1) 定位并提取簇体（检查能否生成 section 头 → Toast 注释区，不含后者） ----
const h = must(lines.findIndex((l) => l.startsWith("// 检查能否生成（工单 a3-readiness-check/01-02）")), "readiness header");
const dashA = h - 1;
if (!lines[dashA].startsWith("// ------")) throw new Error("dash before readiness not found");
const hT = must(lines.findIndex((l) => l.startsWith("// Toast 轻通知（工单 ui-polish-3/03）")), "toast note");
const dashB = hT - 1;
if (!lines[dashB].startsWith("// ------")) throw new Error("dash before toast not found");
const body = lines.slice(dashA, dashB);
const bodyTxt = body.join(eol);
for (const n of ["readinessState", "renderReadinessPanel", "refreshReadinessPanel", "initReadinessCheck"]) {
  if (!new RegExp("function\\s+\\w*\\s*" + n + "\\(").test(bodyTxt)) throw new Error("cluster missing " + n);
}
if (!bodyTxt.includes("stepDoneSet.has(5)")) throw new Error("stepDoneSet.has(5) missing");
if (bodyTxt.includes("setStepsDeps") || bodyTxt.includes("stepsDeps")) throw new Error("cluster must not reference seam");

// ---- 2) 拼装 ui/generate-readiness.js（LF） ----
const header = [
  "// ui/generate-readiness.js — 生成页 · 就绪检查面板（工单 a3-readiness-check/01-02：",
  "// 判据与 btn-generate 前置校验同源——「检查单结论」与「点了生成被拦的提示」",
  "// 永不吵架）DOM 胶水（阶段 2 工单 19，源自 index.html 检查能否生成节）。",
  "//",
  "// 簇体全量迁入：readinessState（判据单源——btn-generate 监听器（host）与",
  "// refreshGenOverview（generate-steps）各自 readiness 判定共用）/ renderReadinessPanel /",
  "// refreshReadinessPanel / initReadinessCheck（按钮 + 容器事件委托：.rc-go 定位 /",
  "// .rc-recommend 一键跑推荐——与「让 AI 推荐」同一入口）。纯件在 fx/readiness.js",
  "//（工单 08 迁）。",
  "// 状态读：A 簇 generate-recommend（chosenPlatform / selectedSlugs /",
  "// setRecommendClarifications / startRecommend）+ ui/step-state.js（stepDoneSet /",
  "// stepCard——工单 12 拥有；issue 所述 generate-steps.js 不实）+",
  "// ui/generate-core.js（desktopTopicOutputEnabled）。",
  "// 跨簇读方：generate-steps.js 经静态 import 调 readinessState（工单 18 的",
  "// setStepsDeps 接缝已由本票取代）；host 经顶部 import 调 readinessState（btn-generate",
  "// 监听器）/ refreshReadinessPanel（setOnStepChange 回调）/ initReadinessCheck（启动区）。",
  'import { $ } from "/js/app.js";',
  'import { generateReadinessChecks, readinessSoftChecks, readinessRowHTML, readinessRowsHTML } from "/js/fx/readiness.js";',
  'import { stepDoneSet, stepCard } from "/js/ui/step-state.js";',
  'import { chosenPlatform, selectedSlugs, setRecommendClarifications, startRecommend } from "/js/ui/generate-recommend.js";',
  'import { desktopTopicOutputEnabled } from "/js/ui/generate-core.js";',
  "",
];
const exportTail = [
  "",
  "// ---- 本簇导出面（host / generate-steps 顶部 import 活绑定调用点） ----",
  "export { readinessState, renderReadinessPanel, refreshReadinessPanel, initReadinessCheck };",
  "",
];
const src = [...header, bodyTxt, ...exportTail].join("\n");
writeFileSync(mod, src, "utf8");
console.log("module written:", mod, "(", src.split("\n").length, "lines )");

// ---- 3) generate-steps.js：接缝 → 静态 import（幂等：已改则跳过） ----
let steps = readFileSync(stepsMod, "utf8");
if (steps.includes("stepsDeps")) {
  const seamRe = /const stepsDeps = \{ readinessState: null \};\r?\n\/\/ readiness 簇服务（host 注册）：refreshGenOverview 的「生成按钮就绪」判定。\r?\n\/\/ 工单 19 迁出 readineess 簇后改静态 import。\r?\nfunction setStepsDeps\(deps\) \{ Object\.assign\(stepsDeps, deps\); \}\r?\n\r?\n/;
  if (!seamRe.test(steps)) throw new Error("steps seam block not found");
  steps = steps.replace(seamRe, "");
  const cCall = steps.split("stepsDeps.readinessState()").length - 1;
  if (cCall !== 1) throw new Error("stepsDeps.readinessState count != 1");
  steps = steps.replace("generateReadinessChecks(stepsDeps.readinessState())",
    "generateReadinessChecks(readinessState())");
  const impAnchor = 'import { generateReadinessChecks } from "/js/fx/readiness.js";';
  if (!steps.includes(impAnchor)) throw new Error("fx readiness import anchor missing");
  steps = steps.replace(impAnchor,
    impAnchor + '\nimport { readinessState } from "/js/ui/generate-readiness.js";  // 工单 19 迁出→静态 import（取代工单 18 接缝）');
  const seamNoteRe = /\/\/ 跨簇服务（host 内联暂不可静态 import）：readinessState（readiness 簇，\r?\n\/\/ 工单 19 迁出后改静态 import）经 setStepsDeps 接缝注册（index.html 启动区）。/;
  if (!seamNoteRe.test(steps)) throw new Error("steps header note not found");
  steps = steps.replace(seamNoteRe,
    "// 跨簇服务（readiness 簇）：readinessState 静态 import 自 ui/generate-readiness.js\n//（工单 19 迁出后由工单 18 的接缝改为静态 import）。");
  const tailRe = /  initGenOverview, refreshGenOverview, runOverviewFill, overviewPlanNow,\r?\n  setStepsDeps };/;
  if (!tailRe.test(steps)) throw new Error("steps export tail not found");
  steps = steps.replace(tailRe,
    "  initGenOverview, refreshGenOverview, runOverviewFill, overviewPlanNow };");
  const noteRef = "//（setOnStepChange 回调）/ setStepsDeps（启动区接缝）。";
  if (!steps.includes(noteRef)) throw new Error("steps export note not found");
  steps = steps.replace(noteRef, "//（setOnStepChange 回调）。");
  if (steps.includes("stepsDeps") || steps.includes("setStepsDeps")) throw new Error("steps seam residual");
  writeFileSync(stepsMod, steps, "utf8");
  console.log("steps rewired: static import from generate-readiness.js");
} else {
  console.log("steps already rewired (skip)");
}

// ---- 4) index.html 手术 ----
{
  const i = must(lines.findIndex((l) => l.includes('from "/js/ui/generate-steps.js"')), "generate-steps import");
  lines[i] = lines[i].replace(", setStepsDeps", "");
  if (lines[i].includes("setStepsDeps")) throw new Error("steps import setStepsDeps residual");
  lines.splice(i + 1, 0,
    'import { readinessState, refreshReadinessPanel, initReadinessCheck } from "/js/ui/generate-readiness.js";');
}
{
  const i = must(lines.findIndex((l) => l.includes("setStepsDeps({ readinessState });")), "setStepsDeps registration");
  lines.splice(i, 1);
}
{
  const i = must(lines.findIndex((l) => l.includes("对 readinessState 的调用经 setStepsDeps 接缝")), "overview note seam text");
  lines[i] = "// refreshGenOverview 对 readinessState 的调用为静态 import（工单 18 接缝已由";
  const i2 = must(lines.findIndex((l) => l.includes("工单 19 迁出 readiness 后改静态 import）")), "overview note seam text 2");
  lines[i2] = "// 工单 19 改静态 import）；变化联动经 setOnStepChange 注册。";
}
{
  const a = must(lines.findIndex((l) => l.startsWith("// 检查能否生成（工单 a3-readiness-check/01-02）")), "readiness header (re)");
  const da = a - 1;
  if (!lines[da].startsWith("// ------")) throw new Error("dash before readiness not found (re)");
  const b = must(lines.findIndex((l) => l.startsWith("// Toast 轻通知（工单 ui-polish-3/03）")), "toast note (re)");
  const db = b - 1;
  if (!lines[db].startsWith("// ------")) throw new Error("dash before toast not found (re)");
  const gap = lines.slice(da, db).join(eol);
  if (!gap.includes("function readinessState() {") || !gap.includes("function initReadinessCheck() {")) throw new Error("re-anchored gap lost cluster?");
  const note = [
    "// ---------------------------------------------------------------------------",
    "// 检查能否生成（工单 a3-readiness-check/01-02）：判据与 btn-generate 前置校验同源",
    "// ---------------------------------------------------------------------------",
    "// 已迁至 static/js/ui/generate-readiness.js（阶段 2 工单 19）：readinessState /",
    "// renderReadinessPanel / refreshReadinessPanel / initReadinessCheck。host 经",
    "// 顶部 import 调 readinessState（btn-generate 监听器）/ refreshReadinessPanel",
    "//（setOnStepChange 回调）/ initReadinessCheck（启动区）；generate-steps 静态",
    "// import readinessState（工单 18 接缝已删除）。",
    "",
  ];
  lines.splice(da, db - da, ...note);
}

// ---- 5) 校验 ----
const out = lines.join(eol);
if ((out.match(/from "\/js\/ui\/generate-readiness\.js"/) || []).length !== 1) throw new Error("generate-readiness import count != 1");
for (const n of ["readinessState", "renderReadinessPanel", "refreshReadinessPanel", "initReadinessCheck"]) {
  if (new RegExp("function\\s+\\w*\\s*" + n + "\\(").test(out)) throw new Error("residual definition of " + n);
}
if (out.includes("setStepsDeps")) throw new Error("setStepsDeps residual in index.html");
if (!out.includes("initReadinessCheck();  // 检查能否生成：按钮 + 检查单面板（事件委托）")) throw new Error("startup initReadinessCheck call lost");
if (!out.includes("setOnStepChange(() => { refreshGenOverview(); refreshReadinessPanel(); });")) throw new Error("setOnStepChange callback lost");
if (!out.includes("const rstate = readinessState();")) throw new Error("btn-generate readinessState call lost");

writeFileSync(p, out, "utf8");
console.log("OK: readiness moved to ui/generate-readiness.js; host rewired; lines now", lines.length);
