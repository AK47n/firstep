// probe-00e-dead-detail.mjs — 12 处真死的逐条现场（工单 module-import-usage/02 的处置依据；只读）。
// 每条给出：所在语句原文、语句里还有谁、剥掉死名后语句是否变空、该模块有几条 import 边
//（判"从清单摘名 / 整条删 / 改裸装载"）。判据走单源 `import-usage.mjs::unusedImports`。
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
  const dead = imports.filter((e) => !e.bare && !e.star && e.names.some((n) => deadNames.has(n)));
  if (!dead.length) continue;
  console.log(`━━ ${key}  （import 边 ${imports.length} 条，裸装载 ${imports.filter((e) => e.bare).length} 条）`);
  for (const edge of dead) {
    const names = edge.names.filter((n) => deadNames.has(n));
    const survivors = edge.names.filter((n) => !deadNames.has(n));
    for (const name of names) {
      console.log(`  ▸ 死名 ${name}  @ 语句 line ${edge.line} ← ${edge.spec}`);
      console.log(`    语句原文（${edge.raw.split("\n").length} 行）：`);
      for (const l of edge.raw.split("\n")) console.log(`      | ${l}`);
      console.log(`    剥掉后剩下的名字：${survivors.length ? survivors.join(", ") : "（空 → 语句整条空）"}`);
      console.log(`    该语句是不是本模块唯一的 import 边：${imports.length === 1 ? "是" : `否（还有 ${imports.length - 1} 条）`}`);
    }
  }
  console.log("");
}
