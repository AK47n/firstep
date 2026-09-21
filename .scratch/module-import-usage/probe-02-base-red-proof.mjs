// probe-02-base-red-proof.mjs — 真红证：把**收走前那个提交**的源码喂进同一套判据（工单 02）。
//
// 「收走前那个提交」= `f1c9e1c7`，**显式钉死，绝不写 HEAD** —— 提交之后 HEAD 就是新代码，
// 红证会**静默变绿**（上一件刚踩过）。所以本件：
//   ① base 自校验：base 必须解析得到、12 处锚点语句逐条还在、级联锚点还在、
//      且 **base 与工作树的差异恰好是本轮改的那 13 个文件**（选错 base 当场大声失败）；
//   ② 判据在 base 上红：**12** 处（逐条点名，标出哪 7 处是旧口径看不见的）；
//   ③ **当前工作树绿（硬判）**：判据 0 处 ＋ 全部既有判据 0 违规；
//   ④ 合成自检（用例表单源在 synthetic-cases.mjs，不抄第二份）。
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  parseModuleImports, listJs, graphBreaks, reachable, wiringViolations, registryProblems,
  bareLoads, unconsumedExports, nonFunctionCallees, exportFaceProblems, starImports,
  readLoadRoot, readConsumerModules,
} from "../../tests/js/boot-contract.mjs";
import { unreachableModules } from "../../tests/js/ui-dom-contract.mjs";
import { unusedImports } from "../../tests/js/import-usage.mjs";
import { syntheticChecks } from "./synthetic-cases.mjs";

const BASE = "f1c9e1c7";                    // ← 显式钉；**不要**改成 HEAD
//   牙齿演示（2026-09-21 实测）：把上面这行改成别的提交，本件会**当场大声失败**——
//   `27a7b46e` 实测三条独立自检同时炸：差异面 58 ≠ 13、base 违规集 13 ≠ 12、base 判据 D = 111 ≠ 0。
const REPO = fileURLToPath(new URL("../../", import.meta.url));
const STATIC = `${REPO}src/contest_generator/static`;
const JS_ROOT = `${STATIC}/js`;
const lines = [];
const say = (s = "") => { lines.push(s); console.log(s); };
const failures = [];
const check = (ok, msg) => { if (!ok) failures.push(msg); return ok; };

const baseBytes = (rel) => execFileSync("git", ["cat-file", "blob", `${BASE}:${rel}`], { cwd: REPO, encoding: "buffer", maxBuffer: 64 * 1024 * 1024 });

// ── 12 处钉死的锚点（模块 / 目标模块 / 死名）——base 上必须逐条还在。
//    与 apply-removal 的锚点表**刻意各留一份**：真红证要自己钉死预期，共用执行器的表等于互相掩护。
const ANCHORS = [
  ["fx/codeview.js", "./highlight.js", "languageOf"],
  ["fx/full-update.js", "./core.js", "downloadedPercent"],
  ["ui/code-compile.js", "/js/ui/generate-mainc-sync.js", "getMainCDiskDir"],
  ["ui/code-tree-ops.js", "/js/ui/codeview.js", "getCodeTreeFiles"],
  ["ui/codeeditor.js", "/js/fx/codeeditor.js", "isTabSavable"],
  ["ui/flash.js", "/js/app.js", "$"],
  ["ui/generate-readiness.js", "/js/fx/readiness.js", "readinessRowHTML"],
  ["ui/generate-tasks.js", "/js/fx/task.js", "resourcesOverviewHTML"],
  ["ui/materials-update.js", "/js/fx/materials-update.js", "aggregateSelection"],
  ["ui/md.js", "/js/app.js", "toastError"],
  ["ui/pdf.js", "/js/fx/pdf.js", "pdfDupRemainText"],
  ["ui/resource-board.js", "/js/fx/resource-board.js", "resourcesToolbarHTML"],
];
/** 期望的违规集（`模块::名字`）——**从锚点推**（同一文件内不抄第二份）。 */
const EXPECTED = ANCHORS.map(([k, , d]) => `${k}::${d}`);
/** 工单 `export-surface-guard/02` §②-3 的"9 处早已死"**点名清单里没有**的那些（7 处）。
 *
 * ⚠ **不是**"旧口径看不见"：实测旧口径（`hostBody` ＋ 按源名）在 base 上同样报出这 7 个
 * （它的 17 处 = 这 12 个名字 ＋ 5 处 `WRITE_GUARD_ACTIONS` 别名误报；见 `survey-00b-criteria-delta.txt`
 * 的"B − A：0 处"）。它们的准确身份是"**同一口径其实也报了、只是工单 02 没点名**"。 */
const NOT_IN_TICKET02_LIST = [
  "fx/codeview.js::languageOf", "fx/full-update.js::downloadedPercent",
  "ui/code-tree-ops.js::getCodeTreeFiles", "ui/flash.js::$",
  "ui/materials-update.js::aggregateSelection", "ui/md.js::toastError",
  "ui/pdf.js::pdfDupRemainText",
];
/** 本轮改动面的 13 个文件（12 处摘名/整条删 ＋ 1 处级联）。 */
const CHANGED = [
  "fx/codeview.js", "fx/core.js", "fx/full-update.js", "ui/code-compile.js", "ui/code-tree-ops.js",
  "ui/codeeditor.js", "ui/flash.js", "ui/generate-readiness.js", "ui/generate-tasks.js",
  "ui/materials-update.js", "ui/md.js", "ui/pdf.js", "ui/resource-board.js",
].map((k) => `src/contest_generator/static/js/${k}`);

// ── 读两个「代」的模块表
const keys = listJs(JS_ROOT).map((p) => p.slice(JS_ROOT.length + 1).split("\\").join("/"));
const relOf = (key) => `src/contest_generator/static/js/${key}`;
const pageOf = (read) => [{ key: "boot.js", text: read("boot.js") },
  ...keys.filter((k) => k !== "boot.js").map((k) => ({ key: k, text: read(k) }))];
const baseRead = (key) => baseBytes(relOf(key)).toString("utf8");
const treeRead = (key) => readFileSync(`${JS_ROOT}/${key}`, "utf8");
const basePage = pageOf(baseRead);
const treePage = pageOf(treeRead);
const consumers = readConsumerModules(REPO);

const violations = (page) => page.flatMap((e) => unusedImports(e.text).flatMap((p) => p.unused.map((n) => `${e.key}::${n}`))).sort();
const criteriaOf = (page) => {
  const boot = page.find((e) => e.key === "boot.js").text;
  const modules = page.filter((e) => e.key !== "boot.js");
  // ui-dom-contract 那条（孤立模块 / import 了却没人调）：本单改了 ui/ 下 8 个模块，必须显式复跑。
  const allModules = page.map((e) => ({ key: `js/${e.key}`, text: e.text }));
  const uiSources = page.filter((e) => e.key.startsWith("ui/")).map((e) => ({ path: e.key, text: e.text }));
  return {
    graphBreaks: graphBreaks(page).length,
    orphans: reachable(boot, modules).orphans.length,
    wiring: wiringViolations(boot, modules).length,
    registry: registryProblems(boot, modules).length,
    bareLoads: bareLoads(boot).length,
    "判据 D": unconsumedExports(page, consumers).length,
    "判据 T": nonFunctionCallees(page).length,
    starImports: starImports(page, consumers).length,
    "取数面体检": exportFaceProblems(page, consumers).length,
    unreachableModules: unreachableModules(uiSources, boot, allModules).length,
  };
};

// 自检锚点表本身：NOT_IN_TICKET02_LIST 必须是 EXPECTED 的 7 元真子集（抄错就当场炸）
check(NOT_IN_TICKET02_LIST.length === 7 && NOT_IN_TICKET02_LIST.every((v) => EXPECTED.includes(v)),
  `NOT_IN_TICKET02_LIST 不是 EXPECTED 的 7 元子集（${NOT_IN_TICKET02_LIST.filter((v) => !EXPECTED.includes(v)).join(", ") || "条数不对"}）`);

// ── ① base 自校验
say("=== ① base 自校验（选错 base 必须当场大声失败）===");
const resolved = execFileSync("git", ["rev-parse", BASE], { cwd: REPO, encoding: "utf8" }).trim();
say(`  base = ${BASE}（解析为 ${resolved}）`);
check(resolved.startsWith(BASE), `base ${BASE} 解析不出来（实得 ${resolved}）`);

// 差异面：base 与工作树的差异必须**恰好**是那 13 个文件
const differing = keys.filter((k) => !baseBytes(relOf(k)).equals(Buffer.from(treeRead(k), "utf8"))).map(relOf);
const diffSet = new Set(differing);
say(`  base 与工作树的差异文件：${differing.length} 个`);
for (const p of differing) say(`    · ${p.replace("src/contest_generator/static/js/", "")}`);
check(differing.length === CHANGED.length && CHANGED.every((p) => diffSet.has(p)),
  `base 与工作树的差异**不是**本轮改的那 ${CHANGED.length} 个文件（实得 ${differing.length} 个）—— base 选错了？`);

// 12 处锚点语句在 base 上逐条还在（内容锚定：目标模块 + 具名清单里含那个死名）
let anchorsOk = 0;
for (const [key, spec, dead] of ANCHORS) {
  const text = baseRead(key);
  const edges = parseModuleImports(text).filter((e) => e.spec === spec);
  const ok = edges.length === 1 && edges[0].names.includes(dead);
  if (ok) anchorsOk++;
  else say(`  ✗ base 上找不到锚点：${key} 的 ${spec} 清单里没有 ${dead}`);
}
check(anchorsOk === 12, `base 上的 12 处锚点只对上 ${anchorsOk} 处`);
const cascadeText = baseRead("fx/core.js");
check(cascadeText.includes("export function downloadedPercent(status) {"), "base 上找不到级联锚点 `export function downloadedPercent(status) {`");
say(`  12 处锚点 ＋ 级联锚点：全部还在 ✓（选错 base 时这几条会先炸）`);
say("");

// ── ② 判据在 base 上红
const baseViolations = violations(basePage);
say(`=== ② 判据在 base 上（${BASE}）===`);
say(`  未使用具名：**${baseViolations.length}** 处（应 ${EXPECTED.length} 处）`);
for (const v of baseViolations) {
  say(`    · ${v}${NOT_IN_TICKET02_LIST.includes(v) ? "   ← 不在工单 02 §②-3 的 9 处点名里" : ""}`);
}
check(baseViolations.length === EXPECTED.length && EXPECTED.every((v) => baseViolations.includes(v)),
  `base 上的违规集与钉死的 12 处不一致（实得 ${baseViolations.length} 处）`);
const baseCriteria = criteriaOf(basePage);
say(`  base 上其余判据：${Object.entries(baseCriteria).map(([k, v]) => `${k}=${v}`).join(" / ")}`);
check(Object.values(baseCriteria).every((v) => v === 0), `base 上既有判据不为 0：${JSON.stringify(baseCriteria)}`);
say("");

// ── ③ 当前工作树绿（**硬判**）
const treeViolations = violations(treePage);
const treeCriteria = criteriaOf(treePage);
say("=== ③ 当前工作树 ===");
say(`  未使用具名：**${treeViolations.length}** 处` + (treeViolations.length ? `（${treeViolations.join(", ")}）` : " ✓"));
say(`  其余判据：${Object.entries(treeCriteria).map(([k, v]) => `${k}=${v}`).join(" / ")}`);
check(treeViolations.length === 0, `工作树上还有 ${treeViolations.length} 处未使用具名`);
check(Object.values(treeCriteria).every((v) => v === 0), `工作树上既有判据不为 0：${JSON.stringify(treeCriteria)}`);
say("");

// ── ④ 合成自检（用例表单源）
const synth = syntheticChecks();
const badSynth = synth.filter((r) => !r.ok);
say("=== ④ 合成自检（synthetic-cases.mjs，与 probe-01 同一张表）===");
say(`  ${synth.length - badSynth.length}/${synth.length} 成立`);
for (const b of badSynth) say(`    ✗ ${b.id}：${b.detail}`);
check(badSynth.length === 0, `合成自检失败 ${badSynth.length} 条`);
say("");
say(failures.length ? `**FAIL**：\n${failures.map((f) => `  ✗ ${f}`).join("\n")}` : "**PASS**");
writeFileSync(fileURLToPath(new URL("./red-proof.txt", import.meta.url)), lines.join("\n") + "\n", "utf8");
process.exit(failures.length ? 1 : 0);
