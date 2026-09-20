// guard-red-proof.mjs — 红证（工单 frontend-import-fossils/01 验收标准 3）。
//
// 手法：把**守卫自己的判据**（`tests/js/import-usage.mjs` 的 `unusedImports`，单源，
// 不另抄一份）作用在 HEAD 版 index.html 上（`git show HEAD:…`），复现"清理前必红"。
// 另存一份**真失败日志**：`guard-run-before.txt`（临时把 HEAD 版落到盘上跑
// `node --test tests/js/import-usage-guard.test.mjs` 的原始输出）。
//
// 用法：node .scratch/frontend-import-fossils/guard-red-proof.mjs
import { execFileSync } from "node:child_process";
import { hostScript, parseImports, unusedImports } from "../../tests/js/import-usage.mjs";

const HEAD_HTML = execFileSync(
  "git",
  ["show", "HEAD:src/contest_generator/static/index.html"],
  { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 }
);

const script = hostScript(HEAD_HTML);
const problems = unusedImports(script);
const names = parseImports(script).reduce((n, i) => n + i.names.length, 0);
const dead = problems.reduce((n, p) => n + p.unused.length, 0);

console.log(`HEAD 版 index.html：import ${parseImports(script).length} 条 / 具名 ${names} 个`);
console.log(`守卫判据在 HEAD 上报出 ${problems.length} 条语句、${dead} 个未使用名字：`);
for (const { spec, unused } of problems) console.log(`  ✗ ${spec}: ${unused.join(", ")}`);
console.log(dead > 0 ? "\nRED（红证成立：清理前守卫必红）" : "\nGREEN（异常：HEAD 上应为红）");
process.exitCode = dead > 0 ? 0 : 1;
