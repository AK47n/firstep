// 阶段 2 工单 17：生成页「修订工坊（revise）」簇迁 static/js/ui/generate-revise.js。
// ① 提取 index.html 2489-2965（修订与深化 section 注释 + revise 状态对象 + 21 函数
//    + 7 监听器）→ 拼装新模块（头部注释 + imports + 导出清单——无接缝/无 setter/
//    无 fx 迁移：tests/js 无 revise 直测，reviseDiffLineHtml / reviseCountQa 保持胶水）；
// ② index.html：簇体→注记（host 对本簇零调用点——监听器随簇迁走，无需新增 import 行）。
// 全程 CRLF 感知；模块文件 LF（与既有 ui/*.js 一致）。
import { readFileSync, writeFileSync, existsSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
const mod = "src/contest_generator/static/js/ui/generate-revise.js";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };
if (lines.some((l) => l.includes('from "/js/ui/generate-revise.js"'))) throw new Error("import already present");
if (existsSync(mod)) throw new Error("module file already exists: " + mod);

// ---- 1) 定位并提取簇体（修订与深化 section 头 → 模块库页 section 头，不含后者） ----
const hRev = must(lines.findIndex((l) => l.startsWith("// 修订与深化阶段卡（工单 revise-deepen/05）")), "revise header");
const dashA = hRev - 1;
if (!lines[dashA].startsWith("// ------")) throw new Error("dash before revise header not found");
const hLib = must(lines.findIndex((l) => l.startsWith("// 模块库页")), "library header");
const dashB = hLib - 1;
if (!lines[dashB].startsWith("// ------")) throw new Error("dash before library header not found");
const body = lines.slice(dashA, dashB);
const bodyTxt = body.join(eol);
const FNS = ["reviseCurrentDir", "reviseCountQa", "renderReviseTelemetry",
  "clearReviseTelemetry", "reviseSetBusy", "reviseResetAll", "reviseLoad",
  "reviseRenderContext", "reviseRunSSE", "reviseRenderDiff", "reviseRenderAnalysis",
  "reviseDiscard", "reviseAnalyze", "reviseApply", "reviseRenderApplyDone",
  "reviseDeepen", "reviseRunDeepen", "reviseRenderVerify", "reviseRenderDeepenDiff",
  "reviseDiffLineHtml", "reviseRollback"];
for (const n of FNS) {
  if (!new RegExp("function\\s+\\w*\\s*" + n + "\\(").test(bodyTxt)) throw new Error("cluster missing " + n);
}
if (!bodyTxt.includes("let revise = {")) throw new Error("revise state object missing");
for (const frag of ['$("btn-revise-session").addEventListener("click", () => {',
  '$("btn-revise-analyze").addEventListener("click", reviseAnalyze);',
  '$("btn-revise-rollback").addEventListener("click", reviseRollback);',
  '$("revise-problem-text").addEventListener("input", () => {']) {
  if (!bodyTxt.includes(frag)) throw new Error("cluster missing listener: " + frag.slice(0, 50));
}
if (bodyTxt.includes("readinessState") || bodyTxt.includes("runCompileOnce(")) throw new Error("cluster depends on host-only or fix-cluster?");
if (bodyTxt.includes("chosenPlatform") || bodyTxt.includes("selectedSlugs")) throw new Error("cluster must not import A-cluster state?");

// ---- 2) 拼装 ui/generate-revise.js（LF；头部注释 + imports + 簇体 + 导出） ----
const header = [
  "// ui/generate-revise.js — 生成页 · 修订与深化阶段卡（工单 revise-deepen/05：",
  "// 加载上下文 / 影响分析 / 确认修订 / 深化 + 编译验证 / 回滚，两段式 API）",
  "// DOM 胶水（阶段 2 工单 17，源自 index.html 修订与深化节）。",
  "//",
  "// 簇体全量迁入：revise 状态对象 + 21 函数（reviseCurrentDir / reviseCountQa /",
  "// renderReviseTelemetry / clearReviseTelemetry / reviseSetBusy / reviseResetAll /",
  "// reviseLoad / reviseRenderContext / reviseRunSSE（独立 SSE 运行器——不共用",
  "// progress.js 面板）/ reviseRenderDiff / reviseRenderAnalysis / reviseDiscard /",
  "// reviseAnalyze / reviseApply / reviseRenderApplyDone / reviseDeepen /",
  "// reviseRunDeepen / reviseRenderVerify / reviseRenderDeepenDiff /",
  "// reviseDiffLineHtml / reviseRollback）+ 7 监听器（btn-revise-session /",
  "// btn-revise-load-dir / revise-dir-input Enter / btn-revise-analyze /",
  "// btn-revise-discard / btn-revise-apply / btn-revise-deepen /",
  "// btn-revise-rollback / revise-problem-text input——import 时绑定：module 脚本",
  "// 延迟执行，DOM 已就绪）。",
  "// 纯件：reviseDiffLineHtml / reviseCountQa / reviseRenderDiff 均为纯计算，",
  "// tests/js 无直测（工单 17 裁定：保持胶水随簇迁，如需直测后续单补——",
  "// 到时按「纯函数迁 fx + fx-guard 登记」先例处理）。",
  "// 依赖：app.js（$ / apiPost / toast）+ fx/core.js（esc）+ fx/llm.js（parseSSE /",
  "// formatLLMTelemetry）+ ui/usage.js（recordLLMUsage）+ ui/step-state.js",
  "//（markStepDone）。无跨簇状态读（本簇状态 = revise 对象私有）；host 对本簇",
  "// 零调用点（监听器全部随簇迁入，无 init 可调）。",
  'import { $, apiPost, toast } from "/js/app.js";',
  'import { esc } from "/js/fx/core.js";',
  'import { parseSSE, formatLLMTelemetry } from "/js/fx/llm.js";',
  'import { recordLLMUsage } from "/js/ui/usage.js";',
  'import { markStepDone } from "/js/ui/step-state.js";',
  "",
];
const exportTail = [
  "",
  "// ---- 本簇导出面（host 零调用点——按工单 17 检查表导出为模块 API） ----",
  "export { reviseLoad, reviseAnalyze, reviseApply, reviseRollback, reviseRunDeepen,",
  "  reviseResetAll, reviseRenderContext };",
  "",
];
const src = [...header, bodyTxt, ...exportTail].join("\n");
writeFileSync(mod, src, "utf8");
console.log("module written:", mod, "(", src.split("\n").length, "lines )");

// ---- 3) index.html：簇体 → 注记 ----
{
  const a = must(lines.findIndex((l) => l.startsWith("// 修订与深化阶段卡（工单 revise-deepen/05）")), "revise header (re)");
  const da = a - 1;
  if (!lines[da].startsWith("// ------")) throw new Error("dash before revise not found (re)");
  const b = must(lines.findIndex((l) => l.startsWith("// 模块库页")), "library header (re)");
  const db = b - 1;
  if (!lines[db].startsWith("// ------")) throw new Error("dash before library not found (re)");
  const gap = lines.slice(da, db).join(eol);
  if (!gap.includes("async function reviseLoad(outputDir) {") || !gap.includes("async function reviseRollback() {")) throw new Error("re-anchored gap lost cluster?");
  const note = [
    "// ---------------------------------------------------------------------------",
    "// 修订与深化阶段卡（工单 revise-deepen/05）：影响分析 → 确认修订 → 可选深化",
    "// + 编译验证 → 回滚",
    "// ---------------------------------------------------------------------------",
    "// 已迁至 static/js/ui/generate-revise.js（阶段 2 工单 17）：revise 状态对象 +",
    "// 21 函数 + 8 监听器（btn-revise-session / btn-revise-load-dir /",
    "// revise-dir-input Enter / btn-revise-analyze / btn-revise-discard /",
    "// btn-revise-apply / btn-revise-deepen / btn-revise-rollback /",
    "// revise-problem-text input）。host 对本簇零调用点（监听器随簇迁入）。",
    "",
  ];
  lines.splice(da, db - da, ...note);
}

// ---- 4) 校验 ----
const out = lines.join(eol);
for (const n of [...FNS, "revise"]) {
  if (n === "revise") {
    if (new RegExp("let\\s+revise\\s*=").test(out)) throw new Error("residual let revise");
  } else if (new RegExp("function\\s+\\w*\\s*" + n + "\\(").test(out)) {
    throw new Error("residual definition of " + n);
  }
}
if (out.includes('$("btn-revise-analyze").addEventListener')) throw new Error("revise listeners should have moved");
if (!out.includes('id="btn-revise-analyze"') && !out.includes('id="btn-revise-session"')) {
  // markup 存在性检查（id="btn-revise-analyze" 是 markup 属性形式）
}
if (!/<button[^>]*id="btn-revise-analyze"/.test(out)) throw new Error("markup id btn-revise-analyze lost");

writeFileSync(p, out, "utf8");
console.log("OK: revise cluster moved to ui/generate-revise.js; lines now", lines.length);
