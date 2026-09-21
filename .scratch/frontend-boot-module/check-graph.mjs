// check-graph.mjs — 现状体检（工单 frontend-boot-module 的 spec 依据，非判据）：
//   ① 全图 import↔export 对账（每条具名 import 是否真有出处）
//   ② 从装载根（收走前那一代 = index.html 宿主块）沿 import 图可达的模块清单
//
// 判据本体**不在这里**：全部 import 自 tests/js/boot-contract.mjs（判据单源）。
// 本文件第一版自带了一份"注释盲"解析器，实测报出 2 处**假断裂**
// （`import { // 注释\n onFileSaved }` 被当成导入名）——那正是"判据抄成两份就分叉"的活证据。
//
// 用法：node .scratch/frontend-boot-module/check-graph.mjs
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { tee } from "./tee.mjs";
import {
  readJsModules, graphBreaks, reachable, parseModuleImports, resolveModuleKey, readLoadRoot,
} from "../../tests/js/boot-contract.mjs";
import { hostScript } from "../../tests/js/import-usage.mjs";

tee(fileURLToPath(import.meta.url), process.argv.slice(2));   // 证据落 UTF-8

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const STATIC = REPO + "src/contest_generator/static/";
// 装载根：搬家之后是 boot.js；还没搬时退回收走前那一代（index.html 宿主块）
const root = readLoadRoot(STATIC)
  || hostScript(execFileSync("git", ["show", "b52022f1:src/contest_generator/static/index.html"],
    { cwd: REPO, encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "pipe"] }));
const modules = readJsModules(STATIC);
console.log(`装载根 = ${readLoadRoot(STATIC) ? "boot.js" : "index.html 宿主块（收走前那一代）"}`);

const breaks = graphBreaks([{ key: "boot.js", text: root }, ...modules]);
console.log(`① 全图 import↔export 对账：${breaks.length} 处断裂`);
for (const b of breaks) {
  console.log(`   ✗ ${b.from} → ${b.spec}：${b.why} ${b.missing.join(", ")}`);
}

const { reachable: seen, orphans } = reachable(root, modules);
console.log(`\n② 装载根可达 ${seen.size} / ${modules.length} 个模块`);
console.log(orphans.length ? `   ✗ 掉队：${orphans.join(", ")}` : "   ✓ 全部可达");
const ui = modules.filter((m) => m.key.startsWith("ui/"));
const fx = modules.filter((m) => m.key.startsWith("fx/"));
console.log(`   （ui ${ui.filter((m) => seen.has(m.key)).length}/${ui.length}，`
  + `fx ${fx.filter((m) => seen.has(m.key)).length}/${fx.length}）`);

const edges = parseModuleImports(root);
console.log(`\n③ 装载根：${edges.length} 条 import（其中裸装载 ${edges.filter((e) => e.bare).length} 条）`
  + `；键空间示例 ${resolveModuleKey(edges[0].spec, "boot.js")}`);
