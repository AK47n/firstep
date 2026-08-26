// 阶段 2 工单 18：生成页「草稿 + 就绪总览」簇迁 static/js/ui/generate-steps.js。
// ① 提取 index.html 两段：A = 草稿（2592-2646：DRAFT_KEY / collectDraftState /
//    draftTimer / scheduleDraftSave / clearDraft / restoreDraft + 清除按钮与
//    4 个 input 顶层监听）；B = 就绪总览（2653-2814：GEN_CRITICAL_STEPS /
//    GEN_RECOMMENDED_STEPS / genOverviewTitles / genOverviewBadges /
//    overviewPlanNow / genOverviewWarn / refreshGenOverview / FOCUS_TARGETS /
//    runOverviewFill / initGenOverview + scroll/resize 监听）→ 拼装新模块；
// ② refreshGenOverview 内 host 内联 readinessState() → 接缝 stepsDeps.readinessState()
//    （setStepsDeps 注册；工单 19 迁出 readiness 后改静态 import）；
// ③ index.html：两段→注记 + host import 行（5 名）+ 启动区 setStepsDeps 注册。
// 注：issue 清单中 stepCard / markStepDone / stepDoneSet / STEP_TOTAL / initStepNav /
// syncStepDone / renderStepProgress / initCardCollapse / CARD_COLLAPSE_SELECTOR 已随
// 工单 12 迁 ui/step-state.js——本单不迁（以 grep 复核为准）；restoreDraft 的
// chosenPlatform 写点工单 12 已改 setChosenPlatform（零残留）。stepDoneSet 拥有者
// = step-state.js（12）——本单无所有权变更。step-done-refs.test.mjs 已于 12 重指向
// generate-recommend.js（文件头注明「cut 方案复核后非 generate-steps」）→ 本单不动。
// 全程 CRLF 感知；模块文件 LF。
import { readFileSync, writeFileSync, existsSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
const mod = "src/contest_generator/static/js/ui/generate-steps.js";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };
if (lines.some((l) => l.includes('from "/js/ui/generate-steps.js"'))) throw new Error("import already present");
if (existsSync(mod)) throw new Error("module file already exists: " + mod);

// ---- 1) 定位并提取两段 ----
const hDraft = must(lines.findIndex((l) => l.startsWith("// 生成页草稿自动记忆（工单 ui-polish-3/01）")), "draft header");
const dashDraft = hDraft - 1;
if (!lines[dashDraft].startsWith("// ------")) throw new Error("dash before draft not found");
const aEnd = must(lines.findIndex((l) => l.startsWith("// 步骤完成集合与顶部进度条（工单 ui-polish-3/02）")), "step-set note");
const dashA = aEnd - 1;
if (!lines[dashA].startsWith("// ------")) throw new Error("dash before step-set note not found");
const bodyA = lines.slice(dashDraft, dashA);   // 2592..2646（含末尾空行）

const hOv = must(lines.findIndex((l) => l.startsWith("// 生成页就绪总览（工单 gen-overview/01）")), "overview header");
const dashOv = hOv - 1;
if (!lines[dashOv].startsWith("// ------")) throw new Error("dash before overview not found");
const bEnd = must(lines.findIndex((l) => l.startsWith("// 最近生成（工单 recent-jobs/01）")), "recent note");
const dashB = bEnd - 1;
if (!lines[dashB].startsWith("// ------")) throw new Error("dash before recent note not found");
const bodyB = lines.slice(dashOv, dashB);   // 2653..2814

const bodyA0 = bodyA.join(eol);
const bodyB0 = bodyB.join(eol);
for (const n of ["collectDraftState", "scheduleDraftSave", "clearDraft", "restoreDraft"]) {
  if (!new RegExp("function\\s+\\w*\\s*" + n + "\\(").test(bodyA0)) throw new Error("bodyA missing " + n);
}
for (const n of ["overviewPlanNow", "genOverviewWarn", "refreshGenOverview",
  "runOverviewFill", "initGenOverview"]) {
  if (!new RegExp("function\\s+\\w*\\s*" + n + "\\(").test(bodyB0)) throw new Error("bodyB missing " + n);
}
if (!bodyA0.includes('const DRAFT_KEY = "firstep.draft.v1";')) throw new Error("DRAFT_KEY missing");
if (!bodyB0.includes("const GEN_CRITICAL_STEPS = [1, 3, 6, 9];")) throw new Error("GEN_CRITICAL_STEPS missing");
if (!bodyB0.includes("const FOCUS_TARGETS = { 1: \"problem\", 9: \"output-dir\" };")) throw new Error("FOCUS_TARGETS missing");
if (!bodyA0.includes('$("btn-clear-draft").addEventListener')) throw new Error("btn-clear-draft listener missing in A?");
if (!bodyB0.includes('$("gen-overview")')) throw new Error("gen-overview wiring missing in B?");
if (bodyA0.includes("chosenPlatform =")) throw new Error("residual chosenPlatform write in draft?");
if (bodyA0.includes("readinessState")) throw new Error("readinessState in draft body?");
const rs = bodyB0.split("readinessState(").length - 1;
if (rs !== 1) throw new Error("readinessState call count != 1 (expect one seam point), got " + rs);

// ---- 2) refreshGenOverview 内 readinessState() → 接缝（特判一次） ----
let bodyB1 = bodyB0.replace(
  "const ready = overviewReadyToGenerate(generateReadinessChecks(readinessState()));",
  "const ready = overviewReadyToGenerate(generateReadinessChecks(stepsDeps.readinessState()));");
if (bodyB1 === bodyB0) throw new Error("readinessState seam replace failed");

// ---- 3) 拼装 ui/generate-steps.js（LF） ----
const header = [
  "// ui/generate-steps.js — 生成页 · 草稿自动记忆 + 就绪总览（阶段 2 工单 18，",
  "// 源自 index.html 生成页草稿与就绪总览两节）。",
  "//",
  "// DM 胶水全量迁入：DRAFT_KEY / DRAFT_FIELDS / collectDraftState / draftTimer /",
  "// scheduleDraftSave / clearDraft / restoreDraft + 清除按钮与 4 个输入顶层监听",
  "//（import 时绑定：module 脚本延迟执行，DOM 已就绪）；GEN_CRITICAL_STEPS /",
  "// GEN_RECOMMENDED_STEPS / genOverviewTitles / genOverviewBadges / overviewPlanNow /",
  "// genOverviewWarn / refreshGenOverview / FOCUS_TARGETS / runOverviewFill /",
  "// initGenOverview（host 启动区调用——scroll/resize/操作区监听在函数内绑定）。",
  "// 状态：本模块无跨簇 mutable 状态；stepDoneSet 拥有者 = ui/step-state.js",
  "//（工单 12），本模块经 import 读；stepCard / stepNavTitles / markStepDone /",
  "// STEP_NAV_CARD_SELECTOR 同（step-state / fx/draft）。",
  "// 跨簇服务（host 内联暂不可静态 import）：readinessState（readiness 簇，",
  "// 工单 19 迁出后改静态 import）经 setStepsDeps 接缝注册（index.html 启动区）。",
  "// 纯件在 fx/*.js（draft / overview / readiness）；A 簇状态读（lastRecommend /",
  "// selectedSlugs）与渲染（renderPlatforms / renderSelected / renderWarnings /",
  "// renderRecommendResult）+ setter（setChosenPlatform / setSelectedSlugs /",
  "// setCurrentTopicId）import 自 ui/generate-recommend.js；desktopTopicOutputEnabled",
  "// import 自 ui/generate-core.js；syncMainCHighlight import 自 ui/generate-mainc.js。",
  'import { $, state } from "/js/app.js";',
  'import { draftState, draftSave, draftLoad, draftRestoreMeta, stepNavTitles } from "/js/fx/draft.js";',
  'import { genOverviewChipsHTML, genOverviewSummaryHTML, overviewFillPlan, overviewReadyToGenerate, hasWarnContent } from "/js/fx/overview.js";',
  'import { generateReadinessChecks } from "/js/fx/readiness.js";',
  'import { stepDoneSet, stepCard, STEP_NAV_CARD_SELECTOR, markStepDone } from "/js/ui/step-state.js";',
  'import { setSelectedSlugs, setChosenPlatform, setCurrentTopicId, renderPlatforms, renderSelected, renderWarnings, renderRecommendResult, lastRecommend, selectedSlugs } from "/js/ui/generate-recommend.js";',
  'import { desktopTopicOutputEnabled } from "/js/ui/generate-core.js";',
  'import { syncMainCHighlight } from "/js/ui/generate-mainc.js";',
  "",
  "const stepsDeps = { readinessState: null };",
  "// readiness 簇服务（host 注册）：refreshGenOverview 的「生成按钮就绪」判定。",
  "// 工单 19 迁出 readineess 簇后改静态 import。",
  "export function setStepsDeps(deps) { Object.assign(stepsDeps, deps); }",
  "",
];
const exportTail = [
  "",
  "// ---- 本簇导出面（host 顶部 import 活绑定调用点） ----",
  "// host 实际使用：restoreDraft（启动区末位）/ initGenOverview（启动区）/",
  "// scheduleDraftSave（A 簇 clusterDeps 注册闭包）/ refreshGenOverview",
  "//（setOnStepChange 回调）/ setStepsDeps（启动区接缝）。",
  "export { restoreDraft, scheduleDraftSave, collectDraftState, clearDraft,",
  "  initGenOverview, refreshGenOverview, runOverviewFill, overviewPlanNow,",
  "  setStepsDeps };",
  "",
];
const src = [...header, bodyA0, "", "// ---------------------------------------------------------------------------\n" +
  "// 就绪总览（与草稿段之间原为步骤完成集合注释——step-state 已于工单 12 迁出）\n" +
  "// ---------------------------------------------------------------------------", "", bodyB1, ...exportTail].join("\n");
if (/(^|[^.])\breadinessState\(/.test(src)) throw new Error("module must not call readinessState directly");
writeFileSync(mod, src, "utf8");
console.log("module written:", mod, "(", src.split("\n").length, "lines )");

// ---- 4) index.html：host import 行（generate-revise 之后）+ 启动区 setStepsDeps ----
{
  const i = must(lines.findIndex((l) => l.includes('from "/js/ui/generate-revise.js"')), "generate-revise import");
  lines.splice(i + 1, 0,
    'import { restoreDraft, scheduleDraftSave, initGenOverview, refreshGenOverview, setStepsDeps } from "/js/ui/generate-steps.js";');
}
{
  const i = must(lines.findIndex((l) => l.includes("setSettingsDeps({ applyToolchains:")), "setSettingsDeps call");
  lines.splice(i + 1, 0,
    "setStepsDeps({ readinessState });  // readiness 簇服务接缝（工单 19 迁出后改静态 import）");
}

// ---- 5) 两段 → 注记 ----
{
  const a = must(lines.findIndex((l) => l.startsWith("// 生成页草稿自动记忆（工单 ui-polish-3/01）")), "draft header (re)");
  const da = a - 1;
  if (!lines[da].startsWith("// ------")) throw new Error("dash before draft not found (re)");
  const aE = must(lines.findIndex((l) => l.startsWith("// 步骤完成集合与顶部进度条（工单 ui-polish-3/02）")), "step-set note (re)");
  const dE = aE - 1;
  if (!lines[dE].startsWith("// ------")) throw new Error("dash before step-set not found (re)");
  const gapA = lines.slice(da, dE).join(eol);
  if (!gapA.includes("function restoreDraft() {") || !gapA.includes("function scheduleDraftSave() {")) throw new Error("re-anchored gapA lost cluster?");
  const noteA = [
    "// ---------------------------------------------------------------------------",
    "// 生成页草稿自动记忆（工单 ui-polish-3/01）：localStorage 防误刷新丢失",
    "// ---------------------------------------------------------------------------",
    "// 已迁至 static/js/ui/generate-steps.js（阶段 2 工单 18）：DRAFT_KEY /",
    "// DRAFT_FIELDS / collectDraftState / draftTimer / scheduleDraftSave /",
    "// clearDraft / restoreDraft + 清除按钮 / 4 输入监听（import 时绑定）。",
    "// host 启动区经顶部 import 调 restoreDraft；A 簇 clusterDeps 注册闭包用",
    "// scheduleDraftSave（host 启动区注册行不变）。",
    "",
  ];
  lines.splice(da, dE - da, ...noteA);
}
{
  const b = must(lines.findIndex((l) => l.startsWith("// 生成页就绪总览（工单 gen-overview/01）")), "overview header (re)");
  const db = b - 1;
  if (!lines[db].startsWith("// ------")) throw new Error("dash before overview not found (re)");
  const bE = must(lines.findIndex((l) => l.startsWith("// 最近生成（工单 recent-jobs/01）")), "recent note (re)");
  const dE = bE - 1;
  if (!lines[dE].startsWith("// ------")) throw new Error("dash before recent not found (re)");
  const gapB = lines.slice(db, dE).join(eol);
  if (!gapB.includes("function refreshGenOverview() {") || !gapB.includes("function initGenOverview() {")) throw new Error("re-anchored gapB lost cluster?");
  const noteB = [
    "// ---------------------------------------------------------------------------",
    "// 生成页就绪总览（工单 gen-overview/01）：顶部步骤 chips + 摘要 + 一键补齐",
    "// ---------------------------------------------------------------------------",
    "// 已迁至 static/js/ui/generate-steps.js（阶段 2 工单 18）：GEN_CRITICAL_STEPS /",
    "// GEN_RECOMMENDED_STEPS / genOverviewTitles / genOverviewBadges /",
    "// overviewPlanNow / genOverviewWarn / refreshGenOverview / FOCUS_TARGETS /",
    "// runOverviewFill / initGenOverview（host 启动区经 import 调）。",
    "// refreshGenOverview 对 readinessState 的调用经 setStepsDeps 接缝（host 注册；",
    "// 工单 19 迁出 readiness 后改静态 import）；变化联动经 setOnStepChange 注册。",
    "",
  ];
  lines.splice(db, dE - db, ...noteB);
}

// ---- 6) 校验 ----
const out = lines.join(eol);
if ((out.match(/from "\/js\/ui\/generate-steps\.js"/) || []).length !== 1) throw new Error("generate-steps import count != 1");
for (const n of ["DRAFT_KEY", "collectDraftState", "scheduleDraftSave", "clearDraft",
  "restoreDraft", "GEN_CRITICAL_STEPS", "overviewPlanNow", "genOverviewWarn",
  "refreshGenOverview", "FOCUS_TARGETS", "runOverviewFill", "initGenOverview"]) {
  if (n === "DRAFT_KEY" || n === "GEN_CRITICAL_STEPS" || n === "FOCUS_TARGETS") {
    if (new RegExp("const\\s+" + n + "\\b").test(out)) throw new Error("residual " + n);
  } else if (new RegExp("function\\s+\\w*\\s*" + n + "\\(").test(out)) {
    throw new Error("residual definition of " + n);
  }
}
if (out.includes('$("btn-clear-draft").addEventListener')) throw new Error("draft listeners should have moved");
if (!out.includes("restoreDraft();  // 草稿恢复放最后：依赖上面全部渲染（平台列表 / 模块池）")) throw new Error("startup restoreDraft call lost");
if (!out.includes("initGenOverview();  // 生成页就绪总览：依赖 stepDoneSet / step-nav current 已就绪（const TDZ）")) throw new Error("startup initGenOverview call lost");
if (!out.includes("setStepsDeps({ readinessState });")) throw new Error("setStepsDeps registration missing");
if (!out.includes("setOnStepChange(() => { refreshGenOverview(); refreshReadinessPanel(); });")) throw new Error("setOnStepChange callback lost");
if (!out.includes("scheduleDraftSave: () => scheduleDraftSave(),")) throw new Error("clusterDeps scheduleDraftSave registration lost");

writeFileSync(p, out, "utf8");
console.log("OK: draft+overview moved to ui/generate-steps.js; host rewired; lines now", lines.length);
