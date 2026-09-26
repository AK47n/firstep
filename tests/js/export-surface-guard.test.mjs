// export-surface-guard.test.mjs — 导出面两条判据进闸门（工单 export-surface-guard/03）。
//
// ## 为什么单开一个守卫文件（而不是接进 fx-guard.test.mjs）
//
// `fx-guard.test.mjs` 的文件头记着"337 行名字表退化"时**如实记账的两条代价**——类型维度与
// 全图零引用的导出。本轮把这两条收回来，但收回来的是**另一个问题**：fx-guard 管的是
// "纯函数有没有回流到 HTML / 装载根"（四条结构不变量），导出面管的是"这条导出谁在用、
// 被用的形态对不对"。一个文件一个职责，判据本体住 `tests/js/boot-contract.mjs`（**单源**），
// 调用点各自成守卫文件——照 `static-import-guard` / `import-usage-guard` / `ui-cycle` 的先例。
// fx-guard 的文件头同步改成"这两条已由本文件守"（工单 03 账本更新）。
//
// ## 判据（工单 01 立，单源 `tests/js/boot-contract.mjs`）
//
//   · **判据 D** —— 每条导出必须被**一条 import 边**消费；消费者 = 页面模块图（含装载根 `boot.js`）
//     ∪ `tests/js` ∪ `tests/browser` 的 `.mjs`。口径是**哪条导出**（`模块::名字`），不是
//     "这个名字还有没有人用"（后者会放过没人取的转手再导出）。
//   · **判据 T** —— 一条 import 边的本地名若在**被导入方**处于调用位，它在导出侧必须解析成
//     **函数形态**；解析跟随 `export { x } from "…"` 再导出链与 `export const x = 别的函数名;`
//     别名链，**解不开按违规算**（不许静默跳过）。
//
// 两条都**零名单**：新增模块、改导出名都不需要登记。红证与 9 条强度自检见
// `.scratch/export-surface-guard/probe-04-red-proof.mjs` / `red-proof.txt`。
//
// ## 消费者集合**不许**排除 `tests/js`（工单 hwcheck-hygiene/01 记账，**只记账、不改口径**）
//
// 评审 P2-12 的建议是"把 `tests/js` 从判据 D 的消费者集合里排除"，理由是那些断言大多是
// 源码串匹配（`readFileSync` + `includes`），算不上"产品侧消费者"。**照字面做会当场红 171 处**：
// 立项前实测（`.scratch/hwcheck-hygiene/probe-dead-exports.mjs` / `.txt`）——
// 消费者全量 **169** 个 → 只留 `tests/browser` 时剩 **11** 个；零消费者导出 **0 → 171**
// （`fx/task.js` 18 / `fx/module.js` 16 / `fx/hwcheck.js` 15 …）。
// 也就是说：判据 D 今天能成立，靠的正是 `tests/js` 那 150+ 条 import 边。
//
// 判据 D 的**产品侧口径**（"每条导出都有一条产品侧 import 边"）要成立，前提是**桥依赖归零**——
// 在那之前，靠 `Object.assign(window, …)` 解析的调用位（`ui/hwcheck.js` 调 `hwcheckErrorHTML`、
// `ui/codeeditor.js` 调 `esc` / `moveTab`）**行为上算消费、判据上不算**，于是"改一处、守一处"的账
// 两处同时对不上。那个方向由 `tests/js/window-bridge-guard.test.mjs` 看着（判据 ⑧）；
// 等这类依赖清零之后，再谈要不要收窄消费者集合。
//
// **别把计数写进判据**：它们是立项那一刻的读数，随每次提交变动。
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import {
  readJsModules, readLoadRoot, readConsumerModules, unconsumedExports, nonFunctionCallees,
  starImports, exportFaceProblems, parseModuleImports, consumptionEdges,
} from "./boot-contract.mjs";

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const STATIC = `${REPO}src/contest_generator/static`;
const MODULES = readJsModules(STATIC);
/** 页面模块表**必须自己把装载根拼在最前面**——`readJsModules` 按文档不含 `boot.js`（体检会拦）。 */
const PAGE = [{ key: "boot.js", text: readLoadRoot(STATIC) }, ...MODULES];
const CONSUMERS = readConsumerModules(REPO);

// 自检用的消费边清单：**用判据本体那一遍遍历**（`consumptionEdges`），不在守卫里另抄一份走图。
const EDGES = consumptionEdges(PAGE, CONSUMERS);
const TAG_COUNT = new Map();          // `模块::名字` 的口径与判据 D 一致（不是"名字级"）
for (const e of EDGES) {
  const tag = `${e.target}::${e.name}`;
  TAG_COUNT.set(tag, (TAG_COUNT.get(tag) || 0) + 1);
}
const patch = (entries, key, fn) => entries.map((e) => (e.key === key ? { ...e, text: fn(e.text) } : e));
const dropName = (text, edge, name) => {
  const rest = edge.names.filter((n) => n !== name);
  return text.replace(edge.raw, rest.length ? `import { ${rest.join(", ")} } from "${edge.spec}";` : "");
};

test("抽取器体检：判据分母都在，且三条下限与「漏喂装载根」真的会报", () => {
  assert.ok(MODULES.length >= 120, `只抽到 ${MODULES.length} 个页面模块（目录结构变了？）`);
  assert.deepEqual(exportFaceProblems(PAGE, CONSUMERS), [],
    "取数面体检自己就红了 —— 判据 D/T 的分母有问题");
  // **正向对照**：断言为空必须能报（先例 ui-dom-contract.test.mjs「那种绿比红更坏」）
  const noRoot = exportFaceProblems(MODULES, CONSUMERS);
  assert.ok(noRoot.some((p) => p.includes("装载根")),
    "漏喂装载根却不报 —— 判据 D 会从 0 假红到 189（实测），而消费侧计数照旧正常");
  const noConsumers = exportFaceProblems(PAGE, []);
  assert.ok(noConsumers.length > 0, "消费侧一个都不喂（判据 D 会整片假红）却不报");
});

test("判据 D：每个导出都得有人 import（零消费者导出 = 0）", () => {
  const dead = unconsumedExports(PAGE, CONSUMERS).map((v) => `  ${v.key}::${v.name}`);
  assert.deepEqual(dead, [],
    "这些导出没有任何 import 边消费它们 —— 要么有人用，要么把 `export` 摘掉（判据单源在\n"
    + "tests/js/boot-contract.mjs；清点先例见工单 export-surface-guard/02）：\n" + dead.join("\n"));
});

test("判据 D 正向对照：注入一个没人 import 的导出必须报出", () => {
  const patched = patch(PAGE, "fx/code.js", (t) => t + "\nexport function probeInjectedDead() {}\n");
  const hit = unconsumedExports(patched, CONSUMERS).some((v) => v.key === "fx/code.js" && v.name === "probeInjectedDead");
  assert.ok(hit, "注入的零消费者导出没被报出（判据静默失效？）");
});

test("判据 D 注释喂绿自检：名字只出现在注释里 → 仍须报出", () => {
  // 工单 frontend-boot-module/05 评审实测过"墓碑注释把判据喂绿"；boot.js 里满是那种注释。
  // 三处都注：声明模块之外的另一模块、装载根（墓碑注释）、**消费侧文件**。
  const CONSUMER_KEY = "tests/js/export-surface-guard.test.mjs";
  let patched = patch(PAGE, "fx/code.js", (t) => t + "\nexport function probeTombstone() {}\n");
  patched = patch(patched, "boot.js", (t) => t + "\n// probeTombstone 已迁至 fx/code.js（墓碑注释，不是消费者）\n");
  patched = patch(patched, "ui/topic.js", (t) => t + "\n// probeTombstone 同上\n");
  const patchedConsumers = patch(CONSUMERS, CONSUMER_KEY, (t) => t + "\n// probeTombstone\n");
  // 注入本身要自检：键写错会让这条自检**静默空转**（双轴评审实测过这个坑）
  assert.ok(patchedConsumers.some((e) => e.key === CONSUMER_KEY && e.text.includes("probeTombstone")),
    `消费侧注释注入没落上（锚点键 \`${CONSUMER_KEY}\` 不存在？）—— 这条自检会静默空转`);
  const hit = unconsumedExports(patched, patchedConsumers).some((v) => v.name === "probeTombstone");
  assert.ok(hit, "名字只出现在注释里却不报 —— 被注释喂绿了");
});

test("判据 D：测试侧的 import 也算消费者（摘掉它必须报出）", () => {
  const anchor = EDGES.find((e) => e.kind === "consumer" && TAG_COUNT.get(`${e.target}::${e.name}`) === 1);
  assert.ok(anchor, "找不到「只被测试侧一条边消费」的锚点 —— 自我检查失效");
  const patched = CONSUMERS.map((e) =>
    (e.key === anchor.entry.key ? { ...e, text: dropName(e.text, anchor.edge, anchor.name) } : e));
  const hit = unconsumedExports(PAGE, patched).some((v) => v.name === anchor.name);
  assert.ok(hit, `${anchor.from} 不再 import ${anchor.name}，判据 D 却没报出（测试缝不算消费者？）`);
});

test("星号导入体检：现状 0 处；注入 `import * as ns` 必须报出", () => {
  assert.deepEqual(starImports(PAGE, CONSUMERS).map((s) => `${s.key} → ${s.spec}`), [],
    "出现触达前端的星号导入 —— 判据 D 的逐名对账对它判不了（`ns.foo()` 在它眼里等于没人用 foo）");
  const patched = patch(PAGE, "boot.js", (t) =>
    t + '\nimport * as probeNs from "/js/fx/code.js";\nprobeNs.maincLineOffsetRange("", 1);\n');
  assert.ok(starImports(patched, CONSUMERS).some((s) => s.spec === "/js/fx/code.js"),
    "注入的星号导入没被体检报出");
});

test("判据 T：调用位的导出都得解析成函数形态（违规 = 0）", () => {
  const bad = nonFunctionCallees(PAGE).map((v) => `  ${v.from} → ${v.to}::${v.name}（${v.form}）`);
  assert.deepEqual(bad, [],
    "这些名字在导入方处于**调用位**，但导出侧不是函数形态（或形态解不开）——\n"
    + "把导出写成函数（`export function` / `= (…) =>` / `= 别的函数名`）或改掉调用：\n" + bad.join("\n"));
});

test("判据 T 形态链：函数别名与再导出链不假红；改成数据必须报出", () => {
  // 锚点先自检：这两行源码形态是**别名链**与**再导出链**的活样本，串变了就得更新本用例
  //（不做成"静默跳过"——那会让这条自检变成真空绿）。
  const ALIAS_LINE = "export const editorLineRange = maincLineOffsetRange;";
  const CHAIN_HEAD = "export function gotoNavTab(tab, focusId) {";
  assert.ok(PAGE.find((e) => e.key === "fx/codeeditor.js").text.includes(ALIAS_LINE),
    `找不到别名链锚点（\`${ALIAS_LINE}\`）—— 更新本用例的锚点`);
  assert.ok(PAGE.find((e) => e.key === "ui/goto-nav.js").text.includes(CHAIN_HEAD),
    `找不到再导出链锚点（\`${CHAIN_HEAD}\`）—— 更新本用例的锚点`);
  // 正向对照（防假红）：这两个名字分别走**别名链**与**再导出链**——两条链不跟通就会假红。
  const violations = nonFunctionCallees(PAGE);
  for (const name of ["editorLineRange", "gotoNavTab"]) {
    assert.ok(!violations.some((v) => v.name === name), `${name} 被判成非函数形态 —— 形态链没跟通（假红）`);
  }
  // 反向：别名那行改成数据 → 必须报出，且 `form` 必须是 **"value"**
  // （不是"解不开"——那才证明形态是**沿别名链解到**的，不是解不开也算违规兜住的）
  const aliasFlipped = patch(PAGE, "fx/codeeditor.js", (t) => t.replace(ALIAS_LINE, "export const editorLineRange = 1;"));
  assert.ok(nonFunctionCallees(aliasFlipped).some((v) => v.name === "editorLineRange" && v.form === "value"),
    "函数别名改成数据后没报出「value」形态（判据 T 对别名链是瞎的，或只报成「解不开」）");
  // 反向：再导出链的**声明处**改成数据 → 必须报出，且那条记录的 `to` 是**再导出方**
  // （`ui/nav-jump.js`）、`form === "value"`：只有真的沿链走到 `ui/goto-nav.js` 的声明处才判得出
  // "value"（链不跟通只会得到"解不开"），这才叫"证明链被跟到了声明处"。
  const chainFlipped = patch(PAGE, "ui/goto-nav.js", (t) =>
    t.replace(CHAIN_HEAD, "export const gotoNavTab = 1; const _probe = (tab, focusId) => {"));
  const chainHits = nonFunctionCallees(chainFlipped).filter((v) => v.name === "gotoNavTab");
  assert.ok(chainHits.some((v) => v.to === "ui/nav-jump.js" && v.form === "value"),
    "再导出链没跟通 —— 翻转声明处后应报出 { to: \"ui/nav-jump.js\", form: \"value\" }，实得 "
    + JSON.stringify(chainHits));
});

test("共享解析器：星号导入必须解析出边（修复前 `import * as ns` 整条被静默丢掉）", () => {
  // 工单 export-surface-guard/01：`parseModuleImports` 原本对 `import * as ns from "…"` 与
  // `export * as ns from "…"` 返回**空数组**（`as` 之后的别名标识符没吃掉，`from` 判在
  // "ns from …" 上）——星号体检没有它就等于空转，故补这条闸门内的直接单测。
  const imported = parseModuleImports('import * as ns from "/js/fx/code.js";');
  assert.equal(imported.length, 1, "`import * as ns from …` 没解析出边");
  assert.equal(imported[0].star, true);
  assert.equal(imported[0].spec, "/js/fx/code.js");
  const reExported = parseModuleImports('export * as ns from "/js/fx/code.js";');
  assert.equal(reExported.length, 1, "`export * as ns from …` 没解析出边");
  assert.equal(reExported[0].star, true);
  const starAll = parseModuleImports('export * from "/js/fx/code.js";');
  assert.equal(starAll.length, 1, "`export * from …` 没解析出边");
  assert.equal(starAll[0].star, true);
  // 反面：具名导入照旧（别把星号分支修成"吞掉下一条语句"）
  const named = parseModuleImports('import { a, b as c } from "/js/fx/code.js";\nimport { d } from "/js/fx/md.js";');
  assert.equal(named.length, 2, "具名导入被星号分支影响");
  assert.deepEqual(named[0].names, ["a", "b"]);
  assert.deepEqual(named[0].locals, ["a", "c"]);
});
