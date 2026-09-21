// probe-01b-face-survey.mjs — 判据取数面读数 ＋ 闸门用例要用的**保守下限**（工单 01）。
// 产出 survey-01-face.txt。
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { parseModuleImports, listJs } from "../../tests/js/boot-contract.mjs";
import { unusedImports } from "../../tests/js/import-usage.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const JS_ROOT = `${STATIC.replace(/[\\/]+$/, "")}/js`;
const files = listJs(JS_ROOT);
let named = 0, stmts = 0, bare = 0, star = 0, withImports = 0, zeroImport = 0;
const deadList = [];
for (const path of files) {
  const key = path.slice(JS_ROOT.length + 1).split("\\").join("/");
  const text = readFileSync(path, "utf8");
  const imports = parseModuleImports(text);
  if (!imports.length) { zeroImport++; continue; }
  withImports++;
  for (const e of imports) {
    stmts++;
    if (e.bare) bare++;
    if (e.star) star++;
    named += e.names.length;
  }
  for (const p of unusedImports(text)) for (const n of p.unused) deadList.push(`${key}::${n}`);
}

const lines = [];
const say = (s = "") => { lines.push(s); console.log(s); };
say("=== module-import-usage/01 取数面读数（判据面 = static/js/**，含 js/ 根 app.js / boot.js）===");
say("");
say(`模块文件数            ${files.length}`);
say(`有 import 边的模块    ${withImports}`);
say(`零 import 的模块      ${zeroImport}`);
say(`import 语句总数       ${stmts}`);
say(`具名导入名字总数      ${named}`);
say(`裸装载（import "…"）  ${bare}`);
say(`星号导入              ${star}`);
say("");
say("闸门用例的**保守下限**（只在抽取器静默失效时才响；不追着现状贴脸）：");
say(`  模块数    >= 120   （实测 ${files.length}）`);
say(`  语句数    >= 400   （实测 ${stmts}）`);
say(`  具名数    >= 1000  （实测 ${named}）`);
say("");
say(`本条判据当前读数（清点是 02 的交付，此刻应为红）：未使用具名 **${deadList.length}** 处`);
for (const d of deadList) say(`  · ${d}`);
writeFileSync(fileURLToPath(new URL("./survey-01-face.txt", import.meta.url)), lines.join("\n") + "\n", "utf8");
