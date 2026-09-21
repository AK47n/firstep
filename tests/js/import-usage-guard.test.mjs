// import-usage-guard.test.mjs — 「零未使用具名 import」不变量（工单 frontend-import-fossils/01；
// 工单 frontend-boot-module/02 重定根到 static/js/boot.js；
// 工单 module-import-usage/01-03 把口径修对、取数面从装载根扩到**每个模块**并接进闸门）。
//
// 这张前端模块图的**唯一装载点**是手写的：69 条 import 里曾有 259 个名字宿主正文一次都
// 没用过（纯函数迁 fx/ 与 tab 迁 ui/ 两轮模块化留下的冻结产物）。代价不是"多几行"，
// 而是**全局失败模式**：删/改其中任一导出，浏览器解析 import 就抛 SyntaxError，
// 整页脚本全灭（2026-09-12 真机现场，服务端全 200）。
//
// 本文件钉住的不变量：**任何模块都不许导入它不使用的名字**（装载根也是模块之一）。
//
// ## 「被使用」的口径（工单 module-import-usage/01，改口径前先读）
//
//   名字要出现在**代码**里：注释 / 字符串 / 正则字面量 / 模板串**文本段**里的同名词**不算**；
//   模板**表达式**里的算（`${esc(x)}` 的 `esc` 是真使用——用 `maskCommentsAndStrings` 会把它
//   误判成死的，照它删就运行时炸，实测 33 处）；**再导出清单**（`export { x };`）算消费；
//   按**本地名**判（`import { A as B }` 看 B，按源名 A 判会误报——实测 5 处）；
//   **裸装载永远合法**（零具名，判据不碰它）。
//
// ## 判据在哪儿
//
//   判据本体在 `tests/js/import-usage.mjs`（单源；红证脚本也 import 它），
//   分词/掩码在 `tests/js/boot-contract.mjs`（唯一一份），
//   **合成用例表**在 `tests/js/import-usage-cases.mjs`（单源：闸门与 `.scratch` 的红证脚本共用同一张表，
//   抄第二份必然分叉——工单 03 的双轴评审实测过一次）。本文件只是**闸门内的调用点**。
//
// 与既有守卫的分工：
//   static-import-guard.test.mjs  装载根清单 ↔ 模块导出对账 + index.html 零 import
//   boot-contract.mjs 的判据        index.html 零定义 / 零裸装载 / 接线不住求值期 / 全图对账
//   export-surface-guard.test.mjs  导出面的反向：每条导出都得有人 import（判据 D / T）
//   本文件                          导入的名字必须真的被用（防化石回流）
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { parseImports, unusedImports } from "./import-usage.mjs";
import { readLoadRoot, readJsModules, bareLoads } from "./boot-contract.mjs";
import { CASES, syntheticChecks } from "./import-usage-cases.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const ROOT = readLoadRoot(STATIC);
assert.ok(ROOT !== null, "找不到装载根 static/js/boot.js");
const IMPORTS = parseImports(ROOT);
/** 判据面：装载根 ＋ `static/js/**` 的全部模块（工单 module-import-usage/01 起）。 */
const MODULES = readJsModules(STATIC);
const ALL = [{ key: "boot.js", text: ROOT }, ...MODULES];

/** 把判据结果拍成 `模块: 名字, 名字` 的人读行。 */
const problemLines = (entries) => entries.flatMap((e) =>
  unusedImports(e.text).map(({ spec, unused }) => `  ${e.key} ← ${spec}: ${unused.join(", ")}`));

// 合成语料（闸门内的假绿反例 / 反向对照）**不住本文件**：用例表单源在
// `tests/js/import-usage-cases.mjs`（闸门与 `.scratch` 的红证脚本共用同一张表；
// 抄第二份必然分叉——工单 03 的双轴评审实测过一次）。见下面的 `syntheticChecks()` 两条用例。

test("抽取器不静默失效：装载清单抽得到、且每条都指向 /js/ 下的模块", () => {
  assert.ok(IMPORTS.length >= 40, `只抽到 ${IMPORTS.length} 条 import（boot.js 结构变了？）`);
  const bad = IMPORTS.filter((i) => !i.spec.startsWith("/js/")).map((i) => i.spec);
  assert.deepEqual(bad, [], `装载清单里出现非 /js/ 说明符：${bad.join(", ")}`);
  const names = IMPORTS.reduce((n, i) => n + i.names.length, 0);
  assert.ok(names >= 50, `具名导入只抽到 ${names} 个（抽取器或清单形态变了）`);
});

test("判据取数面体检：全模块都抽到了，且下限都在（那种绿比红更坏）", () => {
  assert.ok(MODULES.length >= 120, `只抽到 ${MODULES.length} 个模块（目录结构变了？）`);
  const stmts = ALL.reduce((n, e) => n + parseImports(e.text).length, 0);
  const named = ALL.reduce((n, e) => n + parseImports(e.text).reduce((m, i) => m + i.names.length, 0), 0);
  assert.ok(stmts >= 400, `import 语句只抽到 ${stmts} 条（下限 400）——判据会真空绿`);
  assert.ok(named >= 1000, `具名只抽到 ${named} 个（下限 1000）——判据会真空绿`);
  // **正向对照**：往一个真模块里注入一条死 import，判据必须报出（抽取器静默失效要当场红）
  const KEY = "ui/flash.js";
  const INJECT = '\nimport { probeInjectedDead } from "/js/fx/core.js";\n';
  const patched = ALL.map((e) => (e.key === KEY ? { ...e, text: e.text + INJECT } : e));
  assert.ok(patched.some((e) => e.key === KEY && e.text.includes("probeInjectedDead")),
    `注入没落上（锚点键 \`${KEY}\` 不存在？）—— 这条自检会静默空转`);
  const hit = problemLines(patched).some((l) => l.includes("probeInjectedDead"));
  assert.ok(hit, "注入的死 import 没被报出 —— 判据对模块是瞎的（取数面又退回只有装载根？）");
});

test("零未使用具名：装载根 ＋ 全部模块（含 js/ 根的 app.js）", () => {
  const problems = problemLines(ALL);
  assert.deepEqual(
    problems,
    [],
    "这些模块导入了它们用不到的名字 —— 它们不干活，但改名/删除会让整页 SyntaxError。\n"
      + "口径见本文件头（注释/字符串/模板文本段不算使用；模板表达式算；按本地名判）：\n"
      + problems.join("\n")
  );
});

test("合成用例表（单源）：假绿反例必须报出、反向对照必须不报", () => {
  // 用例表在 `tests/js/import-usage-cases.mjs`（**与 .scratch 的红证脚本同一张表**）。
  // 每条用例自带三类断言：判据实得 == 期望 / **注入自检**（语料里 import 之外真的写过那个名字，
  // 防"用例写歪了两边都空"）/ 差分校准（同一语料在旧口径 / naive 掩码 / 朴素子串下的预期）。
  const results = syntheticChecks();
  assert.equal(results.length, CASES.length, "跑出来的用例数与用例表对不上");
  const bad = results.filter((r) => !r.ok);
  assert.deepEqual(
    bad.map((r) => `${r.id}（${r.why}）: ${r.detail}`),
    [],
    "合成用例不成立 —— 判据要么被喂绿、要么假红，要么用例自己在空转：\n"
      + bad.map((r) => `  ${r.id}: ${r.detail}`).join("\n")
  );
});

test("合成用例表：正反两向都有（断言为空必须能报——那种绿比红更坏）", () => {
  // 用例表本身的自检：如果哪天有人把表清空或只留单向，这条当场红。
  const mustReport = CASES.filter((c) => c.expect.length > 0);
  const mustClean = CASES.filter((c) => c.expect.length === 0);
  assert.ok(mustReport.length >= 8, `假绿反例只剩 ${mustReport.length} 条（下限 8）`);
  assert.ok(mustClean.length >= 8, `反向对照只剩 ${mustClean.length} 条（下限 8）`);
  const noSelfCheck = CASES.filter((c) => !(c.bodyIncludes || []).length
    && !String(c.why).includes("一次都没出现") && !String(c.id).includes("bare-load"));
  assert.deepEqual(noSelfCheck.map((c) => c.id), [],
    "这些用例既没有 `bodyIncludes` 注入自检、也不属于「语料本就该零出现」的形态 —— 它们在空转");
  const withCaliber = CASES.filter((c) => c.oldCaliber || c.naiveMask || c.naiveSubstring);
  assert.ok(withCaliber.length >= 8, `带差分校准的用例只剩 ${withCaliber.length} 条（下限 8）`);
});

test("装载根的具名清单非空且无重复名（防 `import {} from` 与重复登记）", () => {
  for (const { spec, names, raw } of IMPORTS) {
    if (!/^[ \t]*import\s*\{/.test(raw)) continue; // 裸 import 归末尾那条「零裸装载」判
    assert.ok(names.length > 0, `${spec} 写成空具名清单`);
    assert.equal(new Set(names).size, names.length, `${spec} 的具名清单里有重复名字`);
  }
});

test("装载根零裸装载（\"靠被加载才接线\"这条隐式边已退场，不许回潮）", () => {
  const bare = bareLoads(ROOT).map((b) => `  ${b.line}: import "${b.spec}"`);
  assert.deepEqual(
    bare,
    [],
    "装载清单里出现裸装载（import \"…\"）—— 那是「这个模块靠被加载才生效」的隐式边：\n"
      + "接线要写成模块导出的 init*()，再由装载根显式调用：\n" + bare.join("\n")
  );
});
