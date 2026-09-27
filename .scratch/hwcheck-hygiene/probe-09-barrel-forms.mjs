// probe-09-barrel-forms.mjs — 工单 hwcheck-hygiene/09 立项量具：
// **barrel（过渡态再导出文件）在四条结构守卫眼里各是什么形态**。
//
// 为什么先量这一步：工单 09 要求"旧 fx/hwcheck.js 仅剩 barrel（再导出）"，
// 而 barrel 有三种写法，四条守卫（判据 D / 判据 T / import-usage / 图对账）不是每种都认。
// 三个合成语料各自只差"再导出怎么写"，其余（消费者 boot.js → barrel → mod.js）逐字相同，
// 于是"哪条守卫认哪种写法"是从读数里读出来的，不是猜的。
//
// 判据本体一行不改：直接调 `boot-contract.mjs` 的 `unconsumedExports` / `nonFunctionCallees` /
// `parseModuleExports` 与 `import-usage.mjs` 的 `unusedImports`（纯函数，模块表进、违规清单出），
// 自带正对照——参考实现（forma，`ui/nav-jump.js` 那一形态）必须四条全绿，否则量具本身失效。
//
// 用法：node .scratch/hwcheck-hygiene/probe-09-barrel-forms.mjs
// 读数：.scratch/hwcheck-hygiene/probe-09-barrel-forms.txt（经 readings.py 落盘）
//
// ## 两份读数（都留着，别只读一份）
//
//   · `probe-09-barrel-forms-before-fix.txt`（2026-09-27 10:08，**改口径前**）：
//     A 行的 import-usage 报 `alpha,beta,gamma`——**这才是"必须动口径"的现场**。
//   · `probe-09-barrel-forms.txt`（同日，**改口径后**）：A 行四条全绿；B 行仍是判据 T 解不开。
//     两份合起来说明：纯 barrel 只有 A 可行，而 A 在旧口径下过不了 import-usage。

import { unusedImports } from "../../tests/js/import-usage.mjs";
import {
  parseModuleExports, unconsumedExports, nonFunctionCallees, graphBreaks,
} from "../../tests/js/boot-contract.mjs";

const MOD = `export function alpha(x) { return x; }
export function beta() { return 1; }
export function gamma() { return 2; }
`;

// 消费者：从**条形文件**import 三个名字，且每个都在**调用位**（判据 D 的消费侧与判据 T 的射程
// 同时落在 barrel 上——第一版语料把 import 指向了 mod.js，于是"判据 T 认不认再导出链"根本没被问到，
// 量出来的全是假读数；这一版是修正后的形态）。
const BOOT = `import { alpha, beta, gamma } from "/js/fx/barrel.js";
alpha(1);
beta();
gamma();
`;

/** 三种再导出写法。三种的**导出名集合相同**（alpha/beta/gamma），差别只在边怎么算。 */
const FORMS = {
  "A export{…}from（纯再导出）": `// barrel
export { alpha, beta, gamma } from "./mod.js";
`,
  "B import + export{…}（本地再导出）": `// barrel
import { alpha, beta, gamma } from "./mod.js";
export { alpha, beta, gamma };
`,
  "C 再导出 + 在正文里真用（ui/nav-jump.js 那一形态）": `// barrel
import { alpha, beta, gamma } from "./mod.js";
export { alpha, beta, gamma } from "./mod.js";
export function allThree() { return alpha(1) + beta() + gamma(); }
`,
};

const page = (barrel) => [
  { key: "boot.js", text: BOOT },
  { key: "fx/barrel.js", text: barrel },
  { key: "fx/mod.js", text: MOD },
];

const fmt = (rows) => (rows.length ? JSON.stringify(rows) : "（零违规）");

console.log("语料：boot.js 从 barrel import { alpha, beta, gamma }，三个都在调用位 → barrel → mod.js\n");
for (const [tag, barrel] of Object.entries(FORMS)) {
  const entries = page(barrel);
  const names = [...parseModuleExports(barrel)].sort();
  const use = unusedImports(barrel);
  const dead = unconsumedExports(entries, []);
  const nonfn = nonFunctionCallees(entries);
  const breaks = graphBreaks(entries);
  console.log(`== ${tag}`);
  console.log(`   导出名         : ${names.join(", ")}`);
  console.log(`   import-usage   : ${fmt(use.map((u) => `${u.spec} → ${u.unused.join(",")}`))}`);
  console.log(`   判据 D 死导出  : ${fmt(dead.map((d) => `${d.key}::${d.name}`))}`);
  console.log(`   判据 T 形态    : ${fmt(nonfn.map((v) => `${v.to}::${v.name}=${v.form}`))}`);
  console.log(`   图对账         : ${fmt(breaks.map((b) => `${b.from}→${b.spec} ${b.why}`))}`);
}

// —— 自证：量具本身要能报，也要能放行 ——
// ① 参考实现（C ＋ 一个取用它那条新导出的消费者）必须四条全绿 —— 否则"某条守卫认哪种写法"
//    这个读数不可信（C 那条 `allThree` 在本语料里没人 import，是**语料缺消费者**，不是形态问题）；
// ② 一个真违规（导出没人 import）必须被判据 D 报出来 —— 否则判据在空转。
const REF = "C 再导出 + 在正文里真用（ui/nav-jump.js 那一形态）";
const ref = [
  { key: "boot.js", text: `${BOOT}allThree();\n`.replace(
    'import { alpha, beta, gamma } from "/js/fx/barrel.js";',
    'import { alpha, beta, gamma, allThree } from "/js/fx/barrel.js";') },
  { key: "fx/barrel.js", text: FORMS[REF] },
  { key: "fx/mod.js", text: MOD },
];
const refClean = unusedImports(FORMS[REF]).length === 0
  && unconsumedExports(ref, []).length === 0
  && nonFunctionCallees(ref).length === 0
  && graphBreaks(ref).length === 0;
const deadProbe = unconsumedExports(
  [...page(FORMS["A export{…}from（纯再导出）"]), { key: "fx/orphan.js", text: "export function nobody() {}\n" }],
  []).some((d) => d.name === "nobody");
console.log("\n自证：");
console.log(`   参考实现（C）四条全绿        : ${refClean ? "OK" : "失效（本量具的结论不可信）"}`);
console.log(`   注入一个零消费者导出 → D 报出 : ${deadProbe ? "OK" : "失效（判据 D 在空转）"}`);
process.exit(refClean && deadProbe ? 0 : 1);
