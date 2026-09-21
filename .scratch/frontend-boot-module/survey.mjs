// survey.mjs — 搬接线前的现场普查（工单 frontend-boot-module 的 spec 依据，非判据）。
//
// 判据/解析全部 import 自 tests/js/boot-contract.mjs（单源；本文件不自己解析 ESM）。
//
// 回答四个问题：
//   ① 收走前 index.html 宿主块的装载清单长什么样（条数 / 具名数 / 裸装载 / 顺序）
//   ② 每个 ui 模块：求值期副作用几条、被谁 import（不含装载根）
//   ③ 哪些是「装载根装载 ＋ 唯一装载来源 ＋ 求值期有接线」（显式 init() 候选；判据③-b 适用面）
//   ④ 装载根里的裸装载（判据③-a 适用面）
//
// 用法：node .scratch/frontend-boot-module/survey.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { tee } from "./tee.mjs";
import {
  readJsModules, parseModuleImports, wiringEffects, importersOf, loadRootKeys,
} from "../../tests/js/boot-contract.mjs";
import { hostScript } from "../../tests/js/import-usage.mjs";

tee(fileURLToPath(import.meta.url), process.argv.slice(2));   // 证据落 UTF-8

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const root = hostScript(readFileSync(STATIC + "index.html", "utf8"));
const modules = readJsModules(STATIC);
const byKey = new Map(modules.map((m) => [m.key, m]));
const loaded = loadRootKeys(root);

const edges = parseModuleImports(root);
const named = edges.reduce((n, e) => n + e.names.length, 0);
console.log(`① 宿主块：${edges.length} 条 import / ${named} 个具名 / ${edges.filter((e) => e.bare).length} 条裸装载`);
edges.forEach((e, n) => console.log(`   ${String(n + 1).padStart(2)}. ${e.spec}${e.bare ? "（裸）" : `  ${e.names.length} 名`}`));

console.log("\n② ui 模块：求值期副作用 / 其它 importer 数 / 是否被装载根装载");
const ui = modules.filter((m) => m.key.startsWith("ui/"));
for (const m of ui) {
  const effects = wiringEffects(m.text).length;
  const others = importersOf(m.key, modules);
  if (!effects && !loaded.has(m.key)) continue;                // 与本次无关的模块不铺开
  console.log(`   ${m.key.padEnd(32)} 副作用 ${String(effects).padStart(2)}  其它 importer ${String(others.size).padStart(2)}  ${loaded.has(m.key) ? "装载根有" : "装载根无"}`);
}

console.log("\n③ ★「装载根装载 ＋ 唯一装载来源 ＋ 求值期有接线」= 显式 init() 候选（判据③-b 的适用面）");
let n = 0;
for (const key of [...loaded].sort()) {
  if (!key.startsWith("ui/")) continue;
  const m = byKey.get(key);
  if (!m || importersOf(key, modules).size > 0) continue;
  const effects = wiringEffects(m.text);
  if (!effects.length) continue;
  n++;
  console.log(`   ★ ${key}：${effects.length} 条（首条 ${effects[0].line}: ${effects[0].text.slice(0, 64)}）`);
}
console.log(`   —— 共 ${n} 个`);

console.log("\n④ 装载根里的裸装载（判据③-a 的适用面）");
for (const e of edges.filter((x) => x.bare)) console.log(`   ○ ${e.line}: import "${e.spec}"`);
