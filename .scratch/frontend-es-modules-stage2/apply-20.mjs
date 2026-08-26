// 阶段 2 工单 20（收尾）：btn-generate 覆盖重发监听器补迁 ui/generate-core.js。
// 该监听器是 index.html 主体最后的大块胶水（工单 15 因 host 内联 readinessState
// 留 host；工单 19 迁出 readiness 后障碍解除）→ 补迁完成「主体 = imports + 页签
// 分发器 + 启动 IIFE + init* 调用」的最终形态。
// ① 提取 index.html 2353-2466（btn-generate 监听器）→ 追加到 generate-core.js
//    （imports 补 readinessState / generateReadinessChecks / collectBindings /
//    generationOutputDirPayload / genStageTexts / fmtWait / isConflictError /
//    conflictDirName / markStepUndone / pythonTemplates / lastRecommend）；
// ② index.html：2246 import 行收敛为 initScoreChecklist（host 其余零调用点——
//    grep 复核）+ 2353-2466 删除 + 注记更新；
// ③ CONTEXT.md「前端纯函数单源」bullet 更新（DOM 胶水单源 = ui/*.js）。
// 全程 CRLF 感知；模块文件 LF。
import { readFileSync, writeFileSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
const coreMod = "src/contest_generator/static/js/ui/generate-core.js";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };

// ---- 1) 提取 btn-generate 监听器 ----
const a = must(lines.findIndex((l) => l.includes('$("btn-generate").addEventListener("click", async () => {')), "btn-generate listener");
const b = a + 1 + must(lines.slice(a + 1).findIndex((l) => l.startsWith("// ---------------------------------------------------------------------------")), "next section dash");
const listenerLines = lines.slice(a, b);   // 2353..2466（含末尾空行）
const listenerTxt = listenerLines.join("\n");
if (!listenerTxt.includes("renderGenerateSuccess(data)") || !listenerTxt.includes("overwrite: true")) {
  throw new Error("listener body incomplete");
}
if (!listenerTxt.includes("readinessState()")) throw new Error("readinessState call missing");

// ---- 2) generate-core.js：imports 补全 + header 注释 + 监听器追加 ----
let core = readFileSync(coreMod, "utf8");
const addImport = (from, to) => {
  if (!core.includes(from)) throw new Error("core import anchor missing: " + from.slice(0, 50));
  core = core.replace(from, to);
};
addImport(
  'import { formatResModules } from "/js/fx/generate.js";',
  'import { formatResModules, collectBindings, generationOutputDirPayload, genStageTexts, fmtWait, isConflictError, conflictDirName } from "/js/fx/generate.js";');
addImport(
  'import { markStepDone } from "/js/ui/step-state.js";',
  'import { markStepDone, markStepUndone } from "/js/ui/step-state.js";');
addImport(
  'import { chosenPlatform, selectedSlugs, expanded, warnings, scorePoints, selectedReferenceIds, autoReferenceIds, currentTopicId } from "/js/ui/generate-recommend.js";',
  'import { chosenPlatform, selectedSlugs, expanded, warnings, scorePoints, selectedReferenceIds, autoReferenceIds, currentTopicId, pythonTemplates, lastRecommend } from "/js/ui/generate-recommend.js";');
addImport(
  'import { refreshRecent } from "/js/ui/recent.js";',
  'import { generateReadinessChecks } from "/js/fx/readiness.js";\nimport { refreshRecent } from "/js/ui/recent.js";\nimport { readinessState } from "/js/ui/generate-readiness.js";');
const headOld = "// 留 host：btn-generate 覆盖重发监听器（依赖 host 内联 readinessState 前置\n// 校验；经顶部 import 调用本模块 renderGenerateSuccess）。";
if (!core.includes(headOld)) throw new Error("core header 留 host note not found");
core = core.replace(headOld,
  "// btn-generate 覆盖重发监听器（工单 20 补迁——readinessState 随工单 19 迁出后");
core = core.replace("// 校验；经顶部 import 调用本模块 renderGenerateSuccess）。", "// 障碍解除，监听器由模块顶层绑定（import 时绑）。");
const tailAnchor = "\n// ---- 本簇导出面（host 顶部 import 活绑定调用点） ----";
if (!core.includes(tailAnchor)) throw new Error("core export tail anchor not found");
core = core.replace(tailAnchor, "\n" + listenerTxt + tailAnchor);
if (!core.includes('$("btn-generate").addEventListener("click", async () => {')) throw new Error("listener not appended");
writeFileSync(coreMod, core, "utf8");
console.log("core updated: btn-generate listener appended");

// ---- 3) index.html：import 收敛 + 注记 + 删除 ----
{
  const i = must(lines.findIndex((l) => l.includes('from "/js/ui/generate-core.js"')), "generate-core import");
  const oldLine = lines[i];
  lines[i] = 'import { initScoreChecklist } from "/js/ui/generate-core.js";';
  if (!oldLine.includes("generateMain") || !oldLine.includes("renderGenerateSuccess")) throw new Error("core import line unexpected");
}
{
  const i = must(lines.findIndex((l) => l.includes("renderGenerateSuccess（btn-generate 覆盖重发监听器）")), "note line 1");
  lines[i] = "// renderGenerateSuccess / desktopTopicOutputEnabled（readiness 检查）——btn-generate";
  const i2 = must(lines.findIndex((l) => l.includes("desktopTopicOutputEnabled（readiness 检查）。btn-generate 监听器留 host。")), "note line 2");
  lines[i2] = "// 覆盖重发监听器亦随迁（工单 20——readinessState 已随工单 19 迁出）。";
}
{
  const a2 = must(lines.findIndex((l) => l.includes('$("btn-generate").addEventListener("click", async () => {')), "btn-generate listener (re)");
  const b2 = a2 + 1 + must(lines.slice(a2 + 1).findIndex((l) => l.startsWith("// ---------------------------------------------------------------------------")), "next section dash (re)");
  const gap = lines.slice(a2, b2).join(eol);
  if (!gap.includes("overwrite: true") || !gap.includes("renderGenerateSuccess(data)")) throw new Error("re-anchored listener lost?");
  const note = [
    "// btn-generate 覆盖重发监听器（readiness 前置校验 / payload 组装 / 覆盖确认）已迁至",
    "// static/js/ui/generate-core.js（阶段 2 工单 20 补迁）——模块顶层绑定。",
    "",
  ];
  lines.splice(a2, b2 - a2, ...note);
}

// ---- 4) 校验 ----
const out = lines.join(eol);
if (out.includes('$("btn-generate").addEventListener("click", async () => {')) throw new Error("host btn-generate listener residual");
if (out.includes("generateMain, renderGenerateSuccess, desktopTopicOutputEnabled")) throw new Error("core import not converged");
if (!out.includes("initScoreChecklist();  // 评分点核对清单：勾选持久化 + 复制核对表（事件委托）")) throw new Error("startup initScoreChecklist lost");
writeFileSync(p, out, "utf8");
console.log("OK: host rewired; lines now", lines.length);
