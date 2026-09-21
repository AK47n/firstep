// apply-removal.mjs — 清点执行器：摘掉 12 处死具名 import ＋ 1 处级联（工单 module-import-usage/02）。
//
// 硬约束（全部由本脚本**自校验**，任何一条不过就**整体拒绝写盘**）：
//   ① 逐处内容锚定：语句按「目标模块 + 具名清单」定位（不是按行号），清单对不上就拒写；
//   ② 摘掉的字串在该语句里必须**恰好出现一次**；
//   ③ 摘完必须能被 `parseModuleImports` 解析出**预期剩下的名字**（不是"看起来对"）；
//   ④ **字节级重放**：取 base `f1c9e1c7` 的**原始字节** → 按锚点独立重算删除区间 → 重放
//      → 必须与该文件**落盘后的原始字节逐字节相等**（不做任何归一化）；
//   ⑤ 行尾写法与**尾部换行**逐文件不变（CRLF/LF 计数、文件末字节序列）；
//   ⑥ 清点后本条判据 = 0，且既有判据（graphBreaks / orphans / wiring / registry / bare /
//      判据 D / 判据 T / 星号 / 取数面）全 0。
//
// 用法：node .scratch/module-import-usage/apply-removal.mjs [--write]
//   不带 --write 只做全部校验并打印（dry-run）；带 --write 才落盘，落盘后立刻复算 ④⑤⑥。
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  parseModuleImports, parseModuleExports, graphBreaks, reachable, wiringViolations,
  registryProblems, bareLoads, unconsumedExports, nonFunctionCallees, exportFaceProblems,
  starImports, readJsModules, readLoadRoot, readConsumerModules, listJs,
} from "../../tests/js/boot-contract.mjs";
import { unreachableModules } from "../../tests/js/ui-dom-contract.mjs";
import { unusedImports } from "../../tests/js/import-usage.mjs";

const BASE = "f1c9e1c7";                       // **显式钉 base**（绝不写 HEAD：提交后 HEAD 就是新代码）
const REPO = fileURLToPath(new URL("../../", import.meta.url));
const WRITE = process.argv.includes("--write");

/** 12 处死具名 import：按「目标模块 + 具名清单」定位（行号只作人读提示）。 */
const NAME_EDITS = [
  { path: "src/contest_generator/static/js/fx/codeview.js", spec: "./highlight.js", names: ["languageOf", "highlightText"], dead: "languageOf" },
  { path: "src/contest_generator/static/js/fx/full-update.js", spec: "./core.js", names: ["esc", "formatSize", "fmtEta", "downloadedPercent", "downloadFailureText", "retryProgressText", "retryNoteText", "SLOW_SPEED_BPS"], dead: "downloadedPercent" },
  { path: "src/contest_generator/static/js/ui/code-compile.js", spec: "/js/ui/generate-mainc-sync.js", names: ["getMainCDiskDir"], dead: "getMainCDiskDir" },
  { path: "src/contest_generator/static/js/ui/code-tree-ops.js", spec: "/js/ui/codeview.js", names: ["refreshCodeTreeOnly", "getCodeTreeFiles", "getCodeTreeDir", "isMainCDiskDir"], dead: "getCodeTreeFiles" },
  { path: "src/contest_generator/static/js/ui/codeeditor.js", spec: "/js/fx/codeeditor.js", names: ["codeTabStripHTML", "codeEditorHTML", "codeWindowRange", "codeWindowSpacerHTML", "conflictHTML", "editorLineRange", "isTabSavable", "dirtySavableTabs", "caretLineOf", "caretColOf", "caretLineFromStarts", "buildLineStarts", "patchLineStarts", "indentOnEnter", "indentLines", "replaceAllText", "replaceOneAt", "EDITOR_TABS_MAX"], dead: "isTabSavable" },
  { path: "src/contest_generator/static/js/ui/flash.js", spec: "/js/app.js", names: ["$", "apiPost", "toast"], dead: "$" },
  { path: "src/contest_generator/static/js/ui/generate-readiness.js", spec: "/js/fx/readiness.js", names: ["generateReadinessChecks", "readinessSoftChecks", "readinessRowHTML", "readinessRowsHTML", "readinessSummaryHTML", "outputDirWarnRow"], dead: "readinessRowHTML" },
  { path: "src/contest_generator/static/js/ui/generate-tasks.js", spec: "/js/fx/task.js", names: ["taskCanFeedback", "taskCardActions", "tasksGridHTML", "tasksProgressText", "tasksOverviewHTML", "resourcesOverviewHTML", "aggregateResourceGroups", "scoreRefsOverviewHTML", "taskStepReportBlocksHTML", "verifyStatusMarkup", "taskDialogButtonHTML", "taskDialogAreaHTML", "nextTaskHint", "taskNextHintHTML", "ideaResultHTML", "globalChatHTML", "globalNoteBadgeHTML", "ideaDraftListHTML", "checklistStateKey", "tasksDoneCount", "unresolvedPrereqs", "taskStatusLabel", "taskChangesHTML", "taskDetailsSnapshot", "taskDetailsRestore"], dead: "resourcesOverviewHTML" },
  { path: "src/contest_generator/static/js/ui/materials-update.js", spec: "/js/fx/materials-update.js", names: ["materialsCheckCardHTML", "aggregateSelection", "materialsPickHTML", "materialsPickFooterHTML", "materialsProgressHTML"], dead: "aggregateSelection" },
  { path: "src/contest_generator/static/js/ui/md.js", spec: "/js/app.js", names: ["$", "apiGet", "toast", "toastError", "copyText"], dead: "toastError" },
  { path: "src/contest_generator/static/js/ui/pdf.js", spec: "/js/fx/pdf.js", names: ["pdfHealth", "pdfBroken", "pdfFilterEntries", "pdfSortEntries", "pdfStats", "pdfStatsText", "pdfChipRowHTML", "pdfRowHTML", "pdfPagesUrl", "pdfPagesText", "pdfDetailHTML", "pdfTrashUrl", "pdfRefsUrl", "pdfTrashMessage", "pdfDupRemainText", "pdfTrashBodyHTML", "pdfFileUrl"], dead: "pdfDupRemainText" },
  { path: "src/contest_generator/static/js/ui/resource-board.js", spec: "/js/fx/resource-board.js", names: ["resourceBoardHTML", "resourcesToolbarHTML", "resourceTaskColorMap"], dead: "resourcesToolbarHTML" },
];

/** 级联 1 处：`downloadedPercent` 的唯一消费者就是上面 `fx/full-update.js` 那条死 import。 */
const CASCADE = {
  path: "src/contest_generator/static/js/fx/core.js",
  anchor: "export function downloadedPercent(status) {",
  remove: "export ",
};

const lines = [];
const say = (s = "") => { lines.push(s); console.log(s); };
const fail = (msg) => { say(`**拒写**：${msg}`); writeReport(); process.exit(1); };

const gitShow = (ref, path) => execFileSync("git", ["show", `${ref}:${path}`], { cwd: REPO, encoding: "buffer", maxBuffer: 64 * 1024 * 1024 });

// ── 0. base 的**唯一**硬要求：它得是"清点前那一代"。核对放在算完锚点之后（见下面的 HEAD 状态核对）。
const changedFiles = [...new Set([...NAME_EDITS.map((e) => e.path), CASCADE.path])];
say(`base = ${BASE}（显式钉；产品面共 ${changedFiles.length} 个文件参与清点）`);

// ── 1. 逐处定位 + 算出删除区间（全部在 base 文本上算）
/** 在 base 文本里按「目标模块 + 具名清单」定位那条语句 → { raw, start, end }。 */
function locateStatement(text, spec, names, path) {
  const hits = parseModuleImports(text).filter((e) => e.spec === spec);
  if (hits.length !== 1) fail(`${path}：说明符 ${spec} 的语句有 ${hits.length} 条（应恰好 1 条）`);
  const edge = hits[0];
  if (JSON.stringify(edge.names) !== JSON.stringify(names)) {
    fail(`${path}：${spec} 的具名清单与锚点不符\n  实得 ${JSON.stringify(edge.names)}\n  应得 ${JSON.stringify(names)}`);
  }
  const start = text.indexOf(edge.raw);
  if (start < 0) fail(`${path}：${spec} 的语句切片在原文里找不到`);
  return { raw: edge.raw, start, end: start + edge.raw.length };
}

/** 整条语句删：从行首（含缩进）删到该行行尾换行（含）。 */
function statementDropRange(text, stmt, path) {
  const nl = text.indexOf("\n", stmt.end);
  const lineTailEnd = nl < 0 ? text.length : nl;
  const restOfLine = text.slice(stmt.end, lineTailEnd);
  if (restOfLine.trim()) fail(`${path}：语句行尾还有别的东西（${JSON.stringify(restOfLine)}）—— 整条删会吃掉它`);
  const from = text.lastIndexOf("\n", stmt.start) + 1;
  if (text.slice(from, stmt.start).trim()) fail(`${path}：语句前面同一行还有别的东西 —— 整条删会吃掉它`);
  return { from, to: nl < 0 ? text.length : nl + 1, what: "整条语句（含该行行尾换行）" };
}

/** 算"把 dead 这个名字从语句里摘掉"的删除区间（按行结构选最小的干净切法）。 */
function removalRange(text, stmt, dead) {
  const raw = stmt.raw;
  const at = raw.indexOf(dead);
  if (at < 0) fail(`语句里找不到 \`${dead}\``);
  if (raw.indexOf(dead, at + 1) >= 0) fail(`语句里 \`${dead}\` 出现不止一次`);
  const lineStart = raw.lastIndexOf("\n", at) + 1;
  const lineEnd = raw.indexOf("\n", at);
  const lineTail = lineEnd < 0 ? raw.length : lineEnd;
  const line = raw.slice(lineStart, lineTail);
  const esc = dead.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // ① 该名字**独占一行**（多行具名清单里的常见形态）→ 连行带缩进与换行一起删
  if (new RegExp(`^\\s*${esc},?\\s*$`).test(line)) {
    if (lineEnd < 0) fail(`\`${dead}\` 独占最后一行且没有换行 —— 形态超出预期`);
    return { from: stmt.start + lineStart, to: stmt.start + lineEnd + 1, what: "整行（该名字独占一行）" };
  }
  // ② 该名字是**本行最后一个项**，且本行前面还有别的项 → 删「前导逗号 + 空格 + 名字」
  //    （名字自己的那个逗号留给下一项；这样不会留下行尾空格）
  if (/^\s*,?\s*$/.test(raw.slice(at + dead.length, lineTail))) {
    const lead = /,\s*$/.exec(raw.slice(lineStart, at));
    if (!lead) fail(`\`${dead}\` 是本行最后一项，但前面找不到分隔逗号`);
    return { from: stmt.start + at - lead[0].length, to: stmt.start + at + dead.length, what: "前导逗号 + 名字（该名字在本行末尾）" };
  }
  // ③ 本行后面还有别的项 → 删「名字 + 逗号 + 逗号后的空格」
  const gap = /^\s*,\s*/.exec(raw.slice(at + dead.length));
  if (gap) return { from: stmt.start + at, to: stmt.start + at + dead.length + gap[0].length, what: "名字 + 后随逗号" };
  fail(`\`${dead}\` 的分隔形态超出预期：${JSON.stringify(raw.slice(at + dead.length, at + dead.length + 20))}`);
  return null;
}

const plan = [];                                // [{ path, ranges: [{from,to,what}], expectNew }]
let bareLoadBranch = 0;                         // 「唯一 import 边 → 改裸装载」支路触发次数（spec 预期 0）
for (const spec of NAME_EDITS) {
  const baseBytes = gitShow(BASE, spec.path);
  const text = baseBytes.toString("utf8");
  if (Buffer.from(text, "utf8").compare(baseBytes) !== 0) fail(`${spec.path}：base 字节不是干净 UTF-8，重放口径不成立`);
  const stmt = locateStatement(text, spec.spec, spec.names, spec.path);
  const expectedSurvivors = spec.names.filter((n) => n !== spec.dead);
  let range;
  if (!expectedSurvivors.length) {
    // 摘完这条语句**整条变空** → 按 spec 的处置规则：该语句是模块唯一 import 边时改裸装载，否则整条删。
    // 本轮实测落在"否则"这一支；若哪天落在"唯一 import 边"那一支，这里**当场拒写**逼人显式决定
    //（不许静默把一个模块变成孤岛）。
    const edges = parseModuleImports(text).length;
    if (edges === 1) { bareLoadBranch++; fail(`${spec.path}：${spec.spec} 是它**唯一**的 import 边 —— 按 spec 应改裸装载，本脚本不代做`); }
    range = statementDropRange(text, stmt, spec.path);
  } else {
    range = removalRange(text, stmt, spec.dead);
  }
  plan.push({ ...spec, baseBytes, text, ranges: [range], expectedSurvivors, expectedExports: null });
}
{
  const baseBytes = gitShow(BASE, CASCADE.path);
  const text = baseBytes.toString("utf8");
  if (Buffer.from(text, "utf8").compare(baseBytes) !== 0) fail(`${CASCADE.path}：base 字节不是干净 UTF-8`);
  const at = text.indexOf(CASCADE.anchor);
  if (at < 0) fail(`${CASCADE.path}：级联锚点找不到：${CASCADE.anchor}`);
  if (text.indexOf(CASCADE.anchor, at + 1) >= 0) fail(`${CASCADE.path}：级联锚点出现不止一次`);
  plan.push({
    path: CASCADE.path, baseBytes, text,
    ranges: [{ from: at, to: at + CASCADE.remove.length, what: "级联：摘 `export ` 前缀" }],
    expectedSurvivors: null, expectedExports: { name: "downloadedPercent", exported: false },
  });
}
const droppedStatements = plan.filter((p) => p.expectedSurvivors && !p.expectedSurvivors.length).length;
const nameEdits = plan.length - 1;
// HEAD 状态核对（**base 选对了吗**）：清点**前** HEAD 应当 == base；清点**后**应当 == base − 删除区间。
// 两种都算对；其它情况（选错 base、或这些文件清点后又被改过）一律拒写。
let headState = "";
for (const p of plan) {
  const headBytes = gitShow("HEAD", p.path);
  const before = headBytes.equals(p.baseBytes);
  const after = headBytes.equals(Buffer.from(applyRanges(p.text, p.ranges), "utf8"));
  if (!before && !after) {
    fail(`base ${BASE} 的 ${p.path} 既不是 HEAD 原样、也不是 HEAD − 删除区间 —— base 选错了，或这些文件清点后又被改过`);
  }
  headState = before ? "清点前（HEAD 未清点）" : "清点后（HEAD 已是清点结果）";
}
say(`HEAD 状态：${headState} —— base 与它的关系对得上 ✓`);
say(`锚点定位：${plan.length} 处 = **摘名 ${nameEdits - droppedStatements}** ＋ **整条删 ${droppedStatements}** ＋ **级联 1**，全部对上 ✓`);
say(`「唯一 import 边 → 改裸装载」支路触发：**${bareLoadBranch} 处**（spec 预期 0；真遇到时本脚本拒写，逼人显式决定）`);
say("");
say("逐处（base 上的删除区间）：");
for (const p of plan) {
  for (const r of p.ranges) {
    const removed = p.text.slice(r.from, r.to);
    say(`  · ${p.path.replace("src/contest_generator/static/js/", "")}  [${r.what}]  删 ${JSON.stringify(removed)}`);
  }
}
say("");

// ── 2. 应用（纯字符区间删除；行尾与尾部换行天然保留）
function applyRanges(text, ranges) {
  let out = text;
  for (const r of [...ranges].sort((a, b) => b.from - a.from)) out = out.slice(0, r.from) + out.slice(r.to);
  return out;
}

const staged = new Map();
for (const p of plan) {
  const next = applyRanges(p.text, p.ranges);
  // ③ 摘完必须解析出**预期剩下的名字**（语句整条删掉时，就必须一条都不剩）
  if (p.expectedSurvivors) {
    const hits = parseModuleImports(next).filter((e) => e.spec === p.spec);
    if (hits.length !== (p.expectedSurvivors.length ? 1 : 0)) {
      fail(`${p.path}：摘完 ${p.spec} 的语句还剩 ${hits.length} 条（应 ${p.expectedSurvivors.length ? 1 : 0} 条）`);
    }
    if (hits.length && JSON.stringify(hits[0].names) !== JSON.stringify(p.expectedSurvivors)) {
      fail(`${p.path}：摘完剩下的名字不对\n  实得 ${JSON.stringify(hits[0].names)}\n  应得 ${JSON.stringify(p.expectedSurvivors)}`);
    }
  }
  // 级联：那条导出必须真的不再导出（而名字仍在本模块里定义）
  if (p.expectedExports) {
    const exported = parseModuleExports(next).has(p.expectedExports.name);
    if (exported !== p.expectedExports.exported) {
      fail(`${p.path}：级联后 ${p.expectedExports.name} 的导出状态仍是 ${exported}`);
    }
  }
  // ⑤ 行尾与尾部换行：**文件末字节序列**与 CR/LF 计数不变
  const tail = (s) => (s.match(/(\r?\n)*$/) || [""])[0];
  if (tail(p.text) !== tail(next)) fail(`${p.path}：尾部换行变了（${JSON.stringify(tail(p.text))} → ${JSON.stringify(tail(next))}）`);
  const countEol = (s) => ({ crlf: (s.match(/\r\n/g) || []).length, lf: (s.match(/(?<!\r)\n/g) || []).length });
  const e0 = countEol(p.text);
  const e1 = countEol(next);
  const removedCrlf = p.ranges.reduce((n, r) => n + (p.text.slice(r.from, r.to).match(/\r\n/g) || []).length, 0);
  const removedLf = p.ranges.reduce((n, r) => n + (p.text.slice(r.from, r.to).match(/(?<!\r)\n/g) || []).length, 0);
  if (e1.crlf !== e0.crlf - removedCrlf || e1.lf !== e0.lf - removedLf) {
    fail(`${p.path}：行尾计数对不上（CRLF ${e0.crlf}→${e1.crlf}，LF ${e0.lf}→${e1.lf}，删除区间里 CRLF ${removedCrlf} / LF ${removedLf}）`);
  }
  staged.set(p.path, { next, baseBytes: p.baseBytes, ranges: p.ranges });
}
say("摘除后自校验：剩下的名字 / 导出状态 / 行尾 / 尾部换行 全部对上 ✓");
say("");

// ── 3. 落盘（--write）或只报意图
if (WRITE) {
  for (const [path, s] of staged) writeFileSync(`${REPO}${path}`, Buffer.from(s.next, "utf8"));
  say(`已落盘 ${staged.size} 个文件（--write）`);
} else {
  say("**dry-run**：未写盘（加 --write 才落盘）");
}
say("");

// ── 4. 字节级重放（独立重算：在 base 字节上按锚点重新定位区间 → 重放 → 比落盘字节）
let replayBad = 0;
say(`=== 字节级重放（base 原始字节 → 按锚点独立重算区间 → 重放 → 比${WRITE ? "**落盘**" : "意图（dry-run 未落盘）"}字节）===`);
for (const path of changedFiles) {
  const baseBytes = gitShow(BASE, path);
  const diskBytes = WRITE ? readFileSync(`${REPO}${path}`) : Buffer.from(staged.get(path).next, "utf8");
  const text = baseBytes.toString("utf8");
  // 独立重算（不复用 plan 里的区间）
  const ranges = [];
  const nameEdit = NAME_EDITS.find((e) => e.path === path);
  if (nameEdit) {
    const stmt = locateStatement(text, nameEdit.spec, nameEdit.names, path);
    const survivors = nameEdit.names.filter((n) => n !== nameEdit.dead);
    ranges.push(survivors.length
      ? removalRange(text, stmt, nameEdit.dead)
      : statementDropRange(text, stmt, path));
  } else {
    const at = text.indexOf(CASCADE.anchor);
    ranges.push({ from: at, to: at + CASCADE.remove.length, what: "级联" });
  }
  const replayed = Buffer.from(applyRanges(text, ranges), "utf8");
  const ok = replayed.equals(diskBytes);
  if (!ok) replayBad++;
  const tailHex = (b) => b.subarray(-6).toString("hex");
  say(`  ${ok ? "PASS" : "FAIL"}  ${path.replace("src/contest_generator/static/js/", "")}`
    + `  字节数 ${baseBytes.length} → ${diskBytes.length}（Δ ${diskBytes.length - baseBytes.length}）`
    + `  末 6 字节 ${tailHex(baseBytes)} → ${tailHex(diskBytes)}`);
}
say(replayBad === 0 ? "**字节级重放：全部相等 ✓**" : `**字节级重放失败 ${replayBad} 个文件 ✗**`);
say("");

// ── 5. 判据复跑（清点后必须全 0）——跑在**清点后的模块表**上（dry-run 也成立）
const STATIC = `${REPO}src/contest_generator/static`;
const KEY_PREFIX = "src/contest_generator/static/js/";
const page = [{ key: "boot.js", text: readLoadRoot(STATIC) }, ...readJsModules(STATIC)]
  .map((e) => (staged.has(KEY_PREFIX + e.key) ? { ...e, text: staged.get(KEY_PREFIX + e.key).next } : e));
const consumers = readConsumerModules(REPO);
const modules = page.filter((e) => e.key !== "boot.js");
const boot = page.find((e) => e.key === "boot.js").text;
// ui-dom-contract 的"孤立模块 / import 了却没人调"判据（键空间是 `js/…`）——本单改了 ui/ 下 8 个模块，
// 必须显式复跑它，不能只靠"前端门禁那一门全绿"间接交代。
const allModules = page.map((e) => ({ key: `js/${e.key}`, text: e.text }));
const uiSources = page.filter((e) => e.key.startsWith("ui/")).map((e) => ({ path: e.key, text: e.text }));
const unusedTotal = page.reduce((n, e) => n + unusedImports(e.text).reduce((m, p) => m + p.unused.length, 0), 0);
const checks = {
  "未使用具名（全模块）": unusedTotal,
  graphBreaks: graphBreaks(page).length,
  orphans: reachable(boot, modules).orphans.length,
  wiring: wiringViolations(boot, modules).length,
  registry: registryProblems(boot, modules).length,
  bareLoads: bareLoads(boot).length,
  "判据 D（零消费者导出）": unconsumedExports(page, consumers).length,
  "判据 T（调用位形态）": nonFunctionCallees(page).length,
  starImports: starImports(page, consumers).length,
  "取数面体检": exportFaceProblems(page, consumers).length,
  "ui-dom-contract：孤立模块 / import 了却没人调": unreachableModules(uiSources, boot, allModules).length,
};
say(`=== 清点后判据复跑（${WRITE ? "落盘后" : "dry-run：跑在**清点后的内存文本**上"}）===`);
let bad = 0;
for (const [k, v] of Object.entries(checks)) {
  if (v !== 0) bad++;
  say(`  ${v === 0 ? "✓" : "✗"} ${k}: ${v}`);
}
say(bad === 0 ? "**全部为 0 ✓**" : `**有 ${bad} 条不为 0 ✗**`);
say("");
say(replayBad === 0 && bad === 0 ? "**应用清点：PASS**" : "**应用清点：FAIL**");

function writeReport() {
  // dry-run 写**另一个文件名**：评审实测过——重跑一次 dry-run 会把已落盘的
  // `verify-removal.txt`（那才是"比落盘字节"的那份证据）覆盖成"比意图字节"，把证据稀释一档。
  const name = WRITE ? "verify-removal.txt" : "verify-removal-dry-run.txt";
  writeFileSync(fileURLToPath(new URL(`./${name}`, import.meta.url)), lines.join("\n") + "\n", "utf8");
}
writeReport();
process.exit(replayBad === 0 && bad === 0 ? 0 : 1);
