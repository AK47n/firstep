// survey2.mjs — 逐模块的**接线清单**（工单 frontend-boot-module 的 spec 依据，非判据）。
//
// 判据/解析全部 import 自 tests/js/boot-contract.mjs（单源）。
// 用途：把 11 个候选模块的"要求值期接线搬进 init 的语句"逐条列出来（工单 03/04 的作业单）。
//
// 用法：node .scratch/frontend-boot-module/survey2.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { tee } from "./tee.mjs";
import {
  readJsModules, parseModuleImports, wiringEffects, importersOf, loadRootKeys,
} from "../../tests/js/boot-contract.mjs";
import { hostScript } from "../../tests/js/import-usage.mjs";

tee(fileURLToPath(import.meta.url), process.argv.slice(2));   // 证据落 UTF-8

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const html = readFileSync(STATIC + "index.html", "utf8");
const root = hostScript(html);
const modules = readJsModules(STATIC);
const loaded = loadRootKeys(root);

// 本次 spec「实现决策」B 档的 11 个模块（裸装载 5 ＋ 唯一来源 6）
const SCOPED = [
  "ui/generate-revise.js", "ui/generate-tasks.js", "ui/params.js", "ui/params-chat.js",
  "ui/delivery.js", "ui/generate-core.js", "ui/library.js", "ui/master.js",
  "ui/reference.js", "ui/topic.js", "ui/code-fix-panel.js",
];

console.log(`装载根：${parseModuleImports(root).length} 条 import，装载 ${loaded.size} 个模块\n`);
let total = 0;
for (const key of SCOPED) {
  const m = modules.find((x) => x.key === key);
  if (!m) { console.log(`✗ ${key} 不在模块表里`); continue; }
  const effects = wiringEffects(m.text);
  const others = [...importersOf(key, modules)];
  total += effects.length;
  console.log(`== ${key}：求值期接线 ${effects.length} 条；其它 importer ${others.length} 个（${others.slice(0, 4).join(", ") || "无"}）`);
  for (const e of effects) console.log(`     ${String(e.line).padStart(5)}: ${e.text.slice(0, 92)}`);
}
console.log(`\n合计 ${total} 条接线话句（11 个模块）`);
