// probe-00b-criteria-delta.mjs — 两种口径的差集（工单 module-import-usage/01 的依据；只读）。
//
// 口径（本件只有"旧口径"需要自持，其余走单源）：
//   A 旧口径（工单 02 用的那个）= `import-usage.mjs::hostBody` 的正文 ＋ 按**源名**判
//     （正文 = 原文 − import 切片 − **整行** `//` 注释；块注释 / 行尾注释 / 字符串全留着）
//   B 本轮判据 = `import-usage.mjs::unusedImports`（`maskNonCode` 正文 ＋ 按**本地名**判）
//
// 清点前的读数：A **17** / B **12**，差集（A − B）**5** 处全是 `WRITE_GUARD_ACTIONS` 别名误报。
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { parseModuleImports, listJs } from "../../tests/js/boot-contract.mjs";
import { unusedImports, hostBody, identRe } from "../../tests/js/import-usage.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const JS_ROOT = `${STATIC.replace(/[\\/]+$/, "")}/js`;

const rowsA = [];
const rowsB = [];
for (const path of listJs(JS_ROOT)) {
  const key = path.slice(JS_ROOT.length + 1).split("\\").join("/");
  const text = readFileSync(path, "utf8");
  const imports = parseModuleImports(text);
  const oldBody = hostBody(text, imports);
  for (const e of imports) {
    if (e.bare || e.star || !e.names.length) continue;
    for (const n of e.names) if (!identRe(n).test(oldBody)) rowsA.push(`${key}::${n}`);
  }
  for (const p of unusedImports(text)) for (const n of p.unused) rowsB.push(`${key}::${n}`);
}

const setA = new Set(rowsA);
const setB = new Set(rowsB);
console.log(`A 口径（工单 02：hostBody ＋ 按源名）：${rowsA.length} 处`);
console.log(`B 口径（本轮：maskNonCode ＋ 按本地名）：${rowsB.length} 处`);
console.log("");
console.log(`A − B（旧口径的假红）：${rowsA.filter((x) => !setB.has(x)).length} 处`);
for (const x of rowsA.filter((x) => !setB.has(x))) console.log(`  · ${x}`);
console.log("");
console.log(`B − A（旧口径看不见的真死）：${rowsB.filter((x) => !setA.has(x)).length} 处`);
for (const x of rowsB.filter((x) => !setA.has(x))) console.log(`  · ${x}`);
console.log("");
console.log("A 口径逐条：");
for (const x of rowsA) console.log(`  · ${x}`);
