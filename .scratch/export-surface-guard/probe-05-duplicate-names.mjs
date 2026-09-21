// probe-05-duplicate-names.mjs — 判据 D 的"名字级"口径到底放过了什么（为读数，不产生判据）
//
// 工单 01 双轴评审（规范轴判断 + spec 轴第 6 条）指出：判据 D 用**全局名字集**判消费，
// 于是"同一个名字被别的模块导出、且那个被消费了"时，本模块的同名导出会漏报。
// 本探针把这件事**量出来**：哪些 (模块, 名字) 是"按模块归属算没人用、按名字算有人用"，
// 且逐条看它到底是不是真的冗余导出。
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  readJsModules, readLoadRoot, readConsumerModules, parseModuleExports, parseModuleImports,
  resolveModuleKey, consumerSpecToKey, unconsumedExports,
} from "../../tests/js/boot-contract.mjs";

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const STATIC = `${REPO}src/contest_generator/static`;
const page = [{ key: "boot.js", text: readLoadRoot(STATIC) }, ...readJsModules(STATIC)];
const consumers = readConsumerModules(REPO);
const pageKeys = new Set(page.map((e) => e.key));
const byKey = new Map(page.map((e) => [e.key, e]));

// 名字级消费集
const nameConsumed = new Set();
const perModuleConsumed = new Map();     // `key::name` → [消费者…]
const note = (key, name, who) => {
  nameConsumed.add(name);
  const tag = `${key}::${name}`;
  if (!perModuleConsumed.has(tag)) perModuleConsumed.set(tag, []);
  perModuleConsumed.get(tag).push(who);
};
for (const entry of page) {
  for (const edge of parseModuleImports(entry.text)) {
    const target = resolveModuleKey(edge.spec, entry.key);
    if (target === null || !pageKeys.has(target)) continue;
    for (const n of edge.names) note(target, n, `page:${entry.key}`);
  }
}
for (const entry of consumers) {
  for (const edge of parseModuleImports(entry.text)) {
    const target = consumerSpecToKey(edge.spec);
    if (target === null || !pageKeys.has(target)) continue;
    for (const n of edge.names) note(target, n, `test:${entry.key}`);
  }
}

/** 本模块是否**声明**了这个名字（`function`/`class`/`const`/`let`/`var`；不看 export 前缀）。 */
const declares = (key, name) => new RegExp(
  `(?:^|\\n)[ \\t]*(?:export\\s+)?(?:async\\s+)?(?:function|class|const|let|var)\\s+`
  + `${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\w$])`).test(byKey.get(key).text);

const nameLevel = unconsumedExports(page, consumers);
const nameLevelSet = new Set(nameLevel.map((v) => `${v.key}::${v.name}`));

// 按模块归属算的违规（不跟再导出链）
const perModule = [];
for (const entry of page) {
  for (const name of parseModuleExports(entry.text)) {
    if (!perModuleConsumed.has(`${entry.key}::${name}`)) perModule.push({ key: entry.key, name });
  }
}

console.log("=== 两种口径的读数 ===");
console.log(`名字级（现实现）：${nameLevel.length} 处`);
console.log(`按模块归属（不跟再导出链）：${perModule.length} 处`);

const extra = perModule.filter((v) => !nameLevelSet.has(`${v.key}::${v.name}`));
console.log(`\n=== 差额 ${extra.length} 处：按模块算没人用、按名字算有人用 ===`);
for (const v of extra) {
  const importedHere = declares(v.key, v.name) ? "本文件声明" : "本文件 import 后再导出";
  const elsewhere = [...perModuleConsumed.entries()]
    .filter(([tag]) => tag.endsWith(`::${v.name}`) && tag !== `${v.key}::${v.name}`)
    .map(([tag, who]) => `${tag}（${who.length} 个消费者）`);
  console.log(`  ${v.key}::${v.name} —— ${importedHere}；同名导出被消费于：${elsewhere.join(" / ") || "（无）"}`);
}

// 逐条看"名字级放过的、按模块算没人用的"里，哪些是真的冗余（没有任何消费者从本模块取它）
console.log(`\n=== 同名的另一些两面都在的读数（供对照）===`);
const dupNames = new Map();
for (const entry of page) {
  for (const name of parseModuleExports(entry.text)) {
    if (!dupNames.has(name)) dupNames.set(name, []);
    dupNames.get(name).push(entry.key);
  }
}
const multi = [...dupNames.entries()].filter(([, keys]) => keys.length > 1);
console.log(`被 ≥2 个模块导出的名字：${multi.length} 个 —— ${multi.map(([n]) => n).join(", ")}`);
for (const [name, keys] of multi) {
  const consumedAt = keys.filter((k) => perModuleConsumed.has(`${k}::${name}`));
  console.log(`  ${name}：导出方 ${keys.length} 个，其中被消费的 ${consumedAt.length} 个`
    + `（未消费：${keys.filter((k) => !consumedAt.includes(k)).join(", ") || "无"}）`);
}

// 再导出链：这些模块的 export 是"从别处转手"的
console.log(`\n=== 差额里"转手再导出"的（本文件没声明）——清点它们等于删一行再导出 ===`);
for (const v of extra.filter((v) => !declares(v.key, v.name))) {
  const edge = parseModuleImports(byKey.get(v.key).text)
    .find((e) => e.names.includes(v.name) && /^export/.test(e.raw.trimStart()));
  console.log(`  ${v.key}::${v.name} —— ${edge ? edge.raw.trim() : "（找不到再导出语句）"}`);
}

// 有没有 python 侧源码文本契约在读这些名字
console.log(`\n=== 差额里被 python/tests 源码文本提到的 ===`);
const hay = [];
const walk = (d) => {
  if (!existsSync(d)) return;
  for (const e of readdirSync(d, { withFileTypes: true })) {
    const full = `${d}/${e.name}`;
    if (e.isDirectory()) walk(full);
    else if (/\.(py|mjs)$/.test(e.name)) hay.push({ path: full, text: readFileSync(full, "utf8") });
  }
};
for (const d of ["tests", "tools", "src"]) walk(`${REPO}${d}`);
for (const v of extra) {
  const hits = hay.filter((f) => new RegExp(`(?<![\\w$.])${v.name}\\b`).test(f.text))
    .map((f) => f.path.slice(REPO.length).split("\\").join("/"))
    .filter((p) => p !== `src/contest_generator/static/js/${v.key}`);
  if (hits.length) console.log(`  ${v.name} → ${hits.join(", ")}`);
}
