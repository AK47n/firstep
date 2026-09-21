// probe-00c-raw-context.mjs — 每条死 import 候选在**原文**里的出现位置（人读证据；只读）。
//
// 为什么要人读一遍：掩码是机器判"在不在代码里"，而"这句话到底算不算用"要看现场
//（当年 `probe-00c` 的第一版把 import 切片替换成**不含换行**的等长空格，行号整体偏移——
//  这里改成保留换行的等长空格，行号不再漂）。
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { parseModuleImports, listJs } from "../../tests/js/boot-contract.mjs";
import { unusedImports } from "../../tests/js/import-usage.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const JS_ROOT = `${STATIC.replace(/[\\/]+$/, "")}/js`;
const only = process.argv[2];

for (const path of listJs(JS_ROOT)) {
  const key = path.slice(JS_ROOT.length + 1).split("\\").join("/");
  if (only && key !== only) continue;
  const text = readFileSync(path, "utf8");
  const imports = parseModuleImports(text);
  const deadNames = new Set(unusedImports(text).flatMap((p) => p.unused));
  if (!deadNames.size) continue;
  const lines = text.split("\n");
  // 原文抹掉 import 切片（**保留换行**，行号不漂）
  let stripped = text;
  let cursor = 0;
  for (const imp of imports) {
    const at = text.indexOf(imp.raw, cursor);
    cursor = at + imp.raw.length;
    stripped = stripped.slice(0, at) + stripped.slice(at, cursor).replace(/[^\n]/g, " ") + stripped.slice(cursor);
  }
  for (const name of deadNames) {
    const re = new RegExp("(?<![\\w$])" + name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?![\\w$])", "g");
    const hits = [];
    for (const m of stripped.matchAll(re)) {
      const line = stripped.slice(0, m.index).split("\n").length;
      hits.push(`${line}: ${(lines[line - 1] || "").trim().slice(0, 130)}`);
    }
    console.log(`▸ ${key}  ${name}`);
    if (!hits.length) console.log("    原文里也零出现 —— 确定死");
    else for (const h of hits) console.log(`    ${h}`);
  }
}
