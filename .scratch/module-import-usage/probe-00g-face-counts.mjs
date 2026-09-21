// probe-00g-face-counts.mjs — 新判据的取数面读数（守卫的下限依据）。
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { parseModuleImports, listJs } from "../../tests/js/boot-contract.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const JS_ROOT = `${STATIC.replace(/[\\/]+$/, "")}/js`;
const files = listJs(JS_ROOT);
let named = 0, stmts = 0, bare = 0, star = 0, modulesWithImports = 0, zeroImport = 0;
const bareList = [];
for (const path of files) {
  const key = path.slice(JS_ROOT.length + 1).split("\\").join("/");
  const imports = parseModuleImports(readFileSync(path, "utf8"));
  if (!imports.length) { zeroImport++; continue; }
  modulesWithImports++;
  for (const e of imports) {
    stmts++;
    if (e.bare) { bare++; bareList.push(`${key}: ${e.spec}`); }
    if (e.star) star++;
    named += e.names.length;
  }
}
console.log(`文件总数（static/js/**，含根 app.js/boot.js）：${files.length}`);
console.log(`有 import 边的模块：${modulesWithImports}；零 import 的模块：${zeroImport}`);
console.log(`import 语句总数：${stmts}`);
console.log(`具名导入名字总数：${named}`);
console.log(`裸装载：${bare}` + (bareList.length ? `\n  ${bareList.join("\n  ")}` : ""));
console.log(`星号导入：${star}`);
