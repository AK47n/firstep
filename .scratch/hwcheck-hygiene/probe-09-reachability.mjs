// probe-09-reachability.mjs — 工单 hwcheck-hygiene/09 的**独立复核**（与
// tests/js/hwcheck-split-integrity.test.mjs 分开算一遍，两边不许互为依据）：
//   ① 六件都从装载根可达（判据④ 的取数面原样跑一遍）；
//   ② window 桥：搬前快照的 77 名 = 六件并集 77 名（逐名相同）；
//   ③ barrel 自己一条桥都不发布、导出 78 名 = 六件导出并集 = 搬前导出数。
// 用法：node .scratch/hwcheck-hygiene/probe-09-reachability.mjs（读数经 readings.py 落盘）
import { readJsModules, readLoadRoot, reachable, windowBridgeNames, parseModuleExports } from "../../tests/js/boot-contract.mjs";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";
const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const MODULES = readJsModules(STATIC);
const boot = readLoadRoot(STATIC);
console.log("掉出模块图的模块:", JSON.stringify(reachable(boot, MODULES).orphans));
const six = ["hwcheck-state", "hwcheck-project", "hwcheck-wiring", "hwcheck-plan", "hwcheck-triage", "hwcheck-handoff"];
const names = new Set();
let union = new Set();
for (const key of six) {
  const m = MODULES.find((x) => x.key === `fx/${key}.js`);
  for (const n of windowBridgeNames(m.text)) names.add(n);
  for (const n of parseModuleExports(m.text)) union.add(n);
}
const snap = readFileSync(".scratch/hwcheck-hygiene/fx-hwcheck-before-split.js", "utf8");
const before = windowBridgeNames(snap);
console.log(`桥：搬前 ${before.size} 名 / 六件并集 ${names.size} 名 / 逐名相同 = ${[...before].sort().join() === [...names].sort().join()}`);
const barrel = MODULES.find((x) => x.key === "fx/hwcheck.js");
console.log(`barrel 发布桥 ${windowBridgeNames(barrel.text).size} 条；barrel 导出 ${parseModuleExports(barrel.text).size} 名`);
console.log(`六件导出并集 ${union.size} 名 / 搬前 ${parseModuleExports(snap).size} 名`);

