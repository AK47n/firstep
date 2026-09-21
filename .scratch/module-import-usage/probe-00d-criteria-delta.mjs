// probe-00d-criteria-delta.mjs — 三种口径的对照读数（工单 module-import-usage/01 的判据依据；只读）。
//
// 口径（**全部走已落地的单源**，本件不抄任何掩码/解析器——评审 Standards 轴点过第一版的重复）：
//   A 旧口径（工单 02）   正文 = 原文 − import − 整行 `//`（`import-usage.mjs::hostBody`），按**源名**判
//   B naive 掩码          正文 = `maskCommentsAndStrings`（模板表达式一并掩掉），按本地名判
//   C 本轮判据            正文 = `maskNonCode`（`import-usage.mjs::unusedImports`），按本地名判
//
// 读数（清点前，工单 02 之前的工作树）：A **17** / B **45** / C **12**
// —— 差集 = B − A 的 33 处是模板表达式假红，A − C 的 5 处是别名假红。历史读数见
// `survey-00-criteria-delta.txt`；清点（工单 02）之后重跑本件会读到 A 5 / B 33+ / C 0。
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { parseModuleImports, maskCommentsAndStrings, listJs } from "../../tests/js/boot-contract.mjs";
import { unusedImports, hostBody, identRe } from "../../tests/js/import-usage.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const JS_ROOT = `${STATIC.replace(/[\\/]+$/, "")}/js`;

const A = [];   // 旧口径：按**源名**判
const B = [];   // naive 掩码：按本地名判
const C = [];   // 本轮判据
for (const path of listJs(JS_ROOT)) {
  const key = path.slice(JS_ROOT.length + 1).split("\\").join("/");
  const text = readFileSync(path, "utf8");
  const imports = parseModuleImports(text);
  const oldBody = hostBody(text, imports);
  for (const e of imports) {
    if (e.bare || e.star || !e.names.length) continue;
    for (const n of e.names) if (!identRe(n).test(oldBody)) A.push(`${key}::${n}`);
  }
  let masked = maskCommentsAndStrings(text);
  let cursor = 0;
  for (const e of imports) {
    const at = text.indexOf(e.raw, cursor);
    cursor = at + e.raw.length;
    masked = masked.slice(0, at) + masked.slice(at, cursor).replace(/[^\n]/g, " ") + masked.slice(cursor);
  }
  for (const e of imports) {
    if (e.bare || e.star || !e.names.length) continue;
    e.names.forEach((n, i) => { if (!identRe(e.locals[i]).test(masked)) B.push(`${key}::${n}`); });
  }
  for (const p of unusedImports(text)) for (const n of p.unused) C.push(`${key}::${n}`);
}

console.log("=== 三种口径对照（判据面 = static/js/**，共 132 个文件）===");
console.log(`A 旧口径（工单 02：hostBody ＋ 按源名）      ${A.length} 处`);
console.log(`B naive 掩码（maskCommentsAndStrings）      ${B.length} 处`);
console.log(`C 本轮判据（maskNonCode ＋ 按本地名）       ${C.length} 处`);
console.log("");
const setA = new Set(A), setC = new Set(C);
console.log(`A − C（旧口径的**假红**：判据说死、其实被用了）：${A.filter((x) => !setC.has(x)).length} 处`);
for (const x of A.filter((x) => !setC.has(x))) console.log(`  · ${x}`);
console.log("");
console.log(`C − A（旧口径看不见的**真死**）：${C.filter((x) => !setA.has(x)).length} 处`);
for (const x of C.filter((x) => !setA.has(x))) console.log(`  · ${x}`);
console.log("");
console.log("C 逐条（= 本轮要处置的全部）：");
for (const x of C) console.log(`  · ${x}`);
