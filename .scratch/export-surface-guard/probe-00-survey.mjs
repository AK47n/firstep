// probe-00-survey.mjs — 导出面普查（只为读数，不产生判据）
// 目标：① 全图零引用的导出到底有几个（backlog 第 10 节记的是 7 个？）
//       ② 其中哪些在模块内部也没人读（= 纯死代码）、哪些在 window 探针桥里
//       ③ 用法派生形态：被 import 的名字在 importer 里处于调用位、而导出侧不是函数形态的有几处
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  readJsModules, readLoadRoot, parseModuleExports, parseModuleImports,
  resolveModuleKey, maskCommentsAndStrings,
} from "../../tests/js/boot-contract.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const boot = readLoadRoot(STATIC);
const modules = readJsModules(STATIC);
const all = [{ key: "boot.js", text: boot }, ...modules];
const byKey = new Map(all.map((m) => [m.key, m]));
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const wordRe = (name) => new RegExp(`(?<![\\w$.])${esc(name)}\\b`);

// —— 导出：模块 → 导出名
const exportsByModule = new Map(all.map((m) => [m.key, [...parseModuleExports(m.text)]]));

// —— 被 import 的源名（全图，含装载根）
const importedNames = new Set();
for (const m of all) {
  for (const e of parseModuleImports(m.text)) {
    if (resolveModuleKey(e.spec, m.key) === null) continue;
    for (const n of e.names) importedNames.add(n);
  }
}

const totalExports = [...exportsByModule.values()].reduce((a, b) => a + b.length, 0);
const dead = [];
for (const [key, names] of exportsByModule) {
  for (const n of names) if (!importedNames.has(n)) dead.push({ key, name: n });
}

/** 名字是否出现在该模块任何 `Object.assign(window, {…})` 里（探针桥）。 */
function bridged(masked, name) {
  for (const m of masked.matchAll(/Object\.assign\(\s*window\s*,\s*\{([\s\S]*?)\}\s*\)/g)) {
    if (wordRe(name).test(m[1])) return true;
  }
  return false;
}

const rows = dead.map(({ key, name }) => {
  const masked = maskCommentsAndStrings(byKey.get(key).text);
  const count = (masked.match(new RegExp(wordRe(name).source, "g")) || []).length;
  return { key, name, occurrences: count, bridged: bridged(masked, name) };
});

console.log("=== 模块表 ===");
console.log(`模块数 ${modules.length}，导出名合计 ${totalExports}`);
console.log(`=== 零 import 引用的导出：${dead.length} 个 ===`);
for (const r of rows) {
  console.log(`  ${r.key.padEnd(26)} ${r.name.padEnd(30)} 本模块出现 ${String(r.occurrences).padStart(2)} 次  探针桥=${r.bridged ? "是" : "否"}`);
}

// —— 仓库其余部分（测试 / 工具 / python）有没有人提这些名字
const hay = [];
const walk = (d) => {
  if (!existsSync(d)) return;
  for (const entry of readdirSync(d, { withFileTypes: true })) {
    const full = `${d}/${entry.name}`;
    if (entry.isDirectory()) walk(full);
    else if (/\.(mjs|js|py|html)$/.test(entry.name)) hay.push({ path: full, text: readFileSync(full, "utf8") });
  }
};
for (const d of ["tests", "tools", "src"]) walk(`${ROOT}${d}`);
console.log("=== 在 tests/ · tools/ · src/ 里被提及的零引用导出 ===");
let anyHit = false;
for (const r of rows) {
  const hits = hay.filter((f) => wordRe(r.name).test(f.text))
    .map((f) => f.path.slice(ROOT.length).split("\\").join("/"))
    .filter((p) => p !== `src/contest_generator/static/js/${r.key}`);
  if (hits.length) { anyHit = true; console.log(`  ${r.name} → ${hits.join(", ")}`); }
}
if (!anyHit) console.log("  （无）");

// —— 用法派生形态：调用位 ⇒ 导出侧必须是函数形态
const FUNC_FORM = (name) => [
  new RegExp(`export\\s+(?:async\\s+)?function\\s+${esc(name)}\\b`),
  new RegExp(`export\\s+const\\s+${esc(name)}\\s*=\\s*(?:async\\s*)?(?:\\(|function\\b|[A-Za-z_$][\\w$]*\\s*=>)`),
  new RegExp(`export\\s+class\\s+${esc(name)}\\b`),
];
let callSites = 0;
const violations = [];
for (const m of all) {
  const masked = maskCommentsAndStrings(m.text);
  for (const e of parseModuleImports(m.text)) {
    const key = resolveModuleKey(e.spec, m.key);
    if (key === null || e.star) continue;
    const target = byKey.get(key);
    if (!target) continue;
    const tmasked = maskCommentsAndStrings(target.text);
    e.locals.forEach((local, idx) => {
      if (!new RegExp(`(?<![\\w$.])${esc(local)}\\s*\\(`).test(masked)) return;
      callSites++;
      const src = e.names[idx];
      if (FUNC_FORM(src).some((re) => re.test(tmasked))) return;
      violations.push({ from: m.key, to: key, name: src });
    });
  }
}
console.log(`=== 调用位导入名 ${callSites} 个；导出侧不是函数形态的 ${violations.length} 处 ===`);
for (const v of violations) console.log(`  ${v.from} ← ${v.to} :: ${v.name}`);
