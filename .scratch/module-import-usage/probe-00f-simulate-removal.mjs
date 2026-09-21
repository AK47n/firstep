// probe-00f-simulate-removal.mjs — **内存模拟**摘掉全部死 import，复跑所有既有判据（只读，不写盘）。
//
// 为什么必须先模拟：摘掉一条 import 边 = 抽掉一个**消费者**。若那是某条导出的**唯一**消费者，
// 判据 D（零消费者导出）会从 0 变成 >0 —— 两张判据当场对撞（工单 module-import-usage/02 的级联
// 就是这么发现的：`fx/core.js::downloadedPercent`）。
// 判据/取数面全部走单源（`boot-contract.mjs` 各判据 ＋ `import-usage.mjs::unusedImports`）。
import { fileURLToPath } from "node:url";
import {
  parseModuleImports, graphBreaks, reachable, wiringViolations, registryProblems, bareLoads,
  unconsumedExports, nonFunctionCallees, exportFaceProblems, starImports,
  readJsModules, readLoadRoot, readConsumerModules,
} from "../../tests/js/boot-contract.mjs";
import { unusedImports } from "../../tests/js/import-usage.mjs";

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));

const readPage = () => [{ key: "boot.js", text: readLoadRoot(STATIC) }, ...readJsModules(STATIC)];
const consumers = readConsumerModules(REPO);
const pick = (page) => ({
  graphBreaks: graphBreaks(page),
  orphans: reachable(page.find((e) => e.key === "boot.js").text, page.filter((e) => e.key !== "boot.js")).orphans,
  wiring: wiringViolations(page.find((e) => e.key === "boot.js").text, page.filter((e) => e.key !== "boot.js")),
  registry: registryProblems(page.find((e) => e.key === "boot.js").text, page.filter((e) => e.key !== "boot.js")),
  bare: bareLoads(page.find((e) => e.key === "boot.js").text),
  D: unconsumedExports(page, consumers),
  T: nonFunctionCallees(page),
  stars: starImports(page, consumers),
  face: exportFaceProblems(page, consumers),
});
const report = (title, r) => {
  console.log(`=== ${title} ===`);
  for (const [k, v] of Object.entries(r)) console.log(`  ${k}: ${Array.isArray(v) ? v.length : v}`);
};

const before = pick(readPage());
report("现状", before);

// 找出所有死名（按模块 + 语句切片归并）
const targets = [];
for (const entry of readPage()) {
  for (const p of unusedImports(entry.text)) {
    for (const name of p.unused) targets.push({ key: entry.key, spec: p.spec, name });
  }
}
console.log(`\n模拟摘除 ${targets.length} 处`);

function simulate(page) {
  const byKeySpec = new Map();
  for (const t of targets) {
    const tag = `${t.key}::${t.spec}`;
    if (!byKeySpec.has(tag)) byKeySpec.set(tag, new Set());
    byKeySpec.get(tag).add(t.name);
  }
  return page.map((entry) => {
    const imports = parseModuleImports(entry.text);
    let text = entry.text;
    const edits = imports
      .map((edge) => ({ edge, dead: byKeySpec.get(`${entry.key}::${edge.spec}`) }))
      .filter(({ edge, dead }) => dead && edge.names.some((n) => dead.has(n)))
      .map(({ edge, dead }) => ({ edge, survivors: edge.names.filter((n) => !dead.has(n)) }));
    for (const { edge, survivors } of edits) {
      const at = text.indexOf(edge.raw);
      if (at < 0) throw new Error(`${entry.key}: 找不到语句切片`);
      if (!survivors.length) {                        // 整条删（连同该行行尾换行）
        const lineStart = text.lastIndexOf("\n", at) + 1;
        const lineEnd = text.indexOf("\n", at + edge.raw.length);
        text = text.slice(0, lineStart) + text.slice(lineEnd < 0 ? text.length : lineEnd + 1);
      } else {
        text = text.slice(0, at) + `import { ${survivors.join(", ")} } from "${edge.spec}";`
          + text.slice(at + edge.raw.length);
      }
    }
    return { ...entry, text };
  });
}

const afterPage = simulate(readPage());
const after = pick(afterPage);
console.log("");
report("模拟摘除后", after);
console.log("");
for (const k of Object.keys(before)) {
  const bn = before[k].length ?? before[k];
  const an = after[k].length ?? after[k];
  if (bn !== an) {
    console.log(`  ⚠ ${k} 变化：${bn} → ${an}`);
    if (Array.isArray(after[k]) && after[k].length) console.log(`     ↳ ${JSON.stringify(after[k]).slice(0, 500)}`);
  }
}
let left = 0;
for (const e of afterPage) {
  const u = unusedImports(e.text);
  if (u.length) { left += u.length; console.log(`  ✗ ${e.key}: ${u.map((x) => x.unused.join(",")).join(" / ")}`); }
}
console.log(`\n模拟后模块级未使用具名：${left} 处`);
