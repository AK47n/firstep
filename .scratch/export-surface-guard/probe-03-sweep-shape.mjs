// probe-03-sweep-shape.mjs — 清扫形态的机械事实（只为读数）
//   ① 页面图与测试侧有没有 `import * as ns`（星号导入会让"逐名消费者"判据判不了）
//   ② 零消费者导出里，几处是 `export {…}` 清单形态（摘名字后清单可能变空 / 整行删）
//   ③ 清单形态里名字从哪来（本文件声明 / 从别处 import 再导出）——后者摘名字会连带
//      产生"未使用具名 import"→ 碰 `import-usage-guard` 的"零未使用具名"
//
// 零消费者那一半**直接用判据本体**（`unconsumedExports` / `starImports`）——工单 01 之后
// 判据单源在 `tests/js/boot-contract.mjs`，探针再抄一份必然分叉（工单 01 双轴评审抓过
// 一次口径分歧：同名导出该按"名字"算还是按"哪条导出"算；也抓到过自抄的形态解析留下的 44 条假红）。
// 形态面（判据 T）的读数不在这里，见 `probe-04-red-proof.mjs`（它跑的就是判据本体）。
import { fileURLToPath } from "node:url";
import {
  readJsModules, readLoadRoot, readConsumerModules, unconsumedExports, starImports,
  parseModuleImports, maskCommentsAndStrings,
} from "../../tests/js/boot-contract.mjs";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const STATIC = `${ROOT}src/contest_generator/static`;
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const pageEntries = [{ key: "boot.js", text: readLoadRoot(STATIC) }, ...readJsModules(STATIC)];
const page = new Map(pageEntries.map((m) => [m.key, m.text]));
const tests = readConsumerModules(ROOT);

// —— ① 星号导入（判据自带的体检）
const stars = starImports(pageEntries, tests);
console.log(`① 触达前端的 \`import * as\`：${stars.length} 处`);
for (const s of stars) console.log(`   ${s.key} → ${s.spec}`);

const zero = unconsumedExports(pageEntries, tests);
console.log(`② 零消费者导出 ${zero.length} 处`);

// —— ③ 形态：inline `export const/function` vs `export {…}` 清单
const shapeOf = (text, name) => {
  const masked = maskCommentsAndStrings(text);
  if (new RegExp(`(?:^|\\n)[ \\t]*export\\s+(?:async\\s+)?(?:function|class|const|let|var)\\s+${esc(name)}(?![\\w$])`).test(masked)) return "inline";
  for (const m of masked.matchAll(/(?:^|\n)[ \t]*export\s*\{([^}]*)\}/g)) {
    const parts = m[1].split(",").map((s) => s.trim().split(/\s+as\s+/).pop().trim()).filter(Boolean);
    if (parts.includes(name)) return "list";
  }
  return "?";
};
const shapes = { inline: [], list: [], unknown: [] };
for (const z of zero) (shapes[shapeOf(page.get(z.key), z.name)] || shapes.unknown).push(`${z.key}::${z.name}`);
console.log(`③ 清扫形态：inline ${shapes.inline.length} 处 / \`export {…}\` 清单 ${shapes.list.length} 处 / 认不出 ${shapes.unknown.length} 处`);
console.log("   清单形态清单：");
for (const s of shapes.list) console.log(`     ${s}`);
if (shapes.unknown.length) { console.log("   认不出："); for (const s of shapes.unknown) console.log(`     ${s}`); }

// 清单形态里，名字是不是从别处 import 来的（摘掉再导出会让 import 变未使用 → 门禁红）
console.log("   清单形态的来源（本文件声明 / 从别处 import 再导出）：");
for (const s of shapes.list) {
  const [key, name] = s.split("::");
  const edge = parseModuleImports(page.get(key))
    .find((e) => e.names.includes(name) && /^export/.test(e.raw.trimStart()));
  const imported = parseModuleImports(page.get(key)).find((e) => e.locals.includes(name));
  console.log(`     ${s} → ${edge ? `再导出语句「${edge.raw.trim()}」` : "本文件声明"}`
    + `${imported ? `；本地名来自 ${imported.spec}` : ""}`);
}

// 清单是否会因摘名字变空（空则整行删）
console.log("   清单摘完会不会变空：");
for (const key of new Set(shapes.list.map((s) => s.split("::")[0]))) {
  const masked = maskCommentsAndStrings(page.get(key));
  for (const m of masked.matchAll(/(?:^|\n)[ \t]*export\s*\{([^}]*)\}[^\n]*/g)) {
    const parts = m[1].split(",").map((s) => s.trim().split(/\s+as\s+/).pop().trim()).filter(Boolean);
    const doomed = parts.filter((n) => shapes.list.includes(`${key}::${n}`));
    if (!doomed.length) continue;
    console.log(`     ${key}：清单 ${parts.length} 项，其中 ${doomed.length} 项要摘`
      + ` → ${doomed.length === parts.length ? "**整行删**" : "摘名字，行留下"}`);
  }
}
