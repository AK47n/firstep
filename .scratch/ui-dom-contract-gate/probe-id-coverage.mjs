// 探针 v3：ui 静态引用的 id，在「index.html 的静态声明 ∪ 全前端源码里的
// id="…" 字面量（模板串内联）∪ createElement 后赋 .id = "…"」里找不到 = 真死引用。
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const read = (p) => readFileSync(p, "utf8");

function allJs(dir) {
  const out = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = dir + "/" + e.name;
    if (e.isDirectory()) out.push(...allJs(p));
    else if (e.name.endsWith(".js")) out.push(p);
  }
  return out;
}

const html = read(STATIC + "index.html");
const declared = new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]));

const jsFiles = allJs(STATIC + "js");
const source = jsFiles.map((p) => read(p)).join("\n");
// 模板串里的 id="…" 与 JS 里赋 .id = "…"
const declaredInJs = new Set([
  ...[...source.matchAll(/id="([A-Za-z][\w-]*)"/g)].map((m) => m[1]),
  ...[...source.matchAll(/\.id\s*=\s*"([A-Za-z][\w-]*)"/g)].map((m) => m[1]),
  ...[...source.matchAll(/\bid:\s*"([A-Za-z][\w-]*)"/g)].map((m) => m[1]),
]);
const allDeclared = new Set([...declared, ...declaredInJs]);

const refs = new Map();
const PATTERNS = [
  /\$\(\s*"([A-Za-z][\w-]*)"\s*\)/g,
  /getElementById\(\s*"([A-Za-z][\w-]*)"\s*\)/g,
  /querySelector(?:All)?\(\s*"#([A-Za-z][\w-]*)(?:[\s"'.>[:\[]|$)/g,
];
for (const p of jsFiles.filter((p) => p.includes("/ui/"))) {
  const src = read(p);
  for (const re of PATTERNS) {
    for (const m of src.matchAll(re)) {
      if (!refs.has(m[1])) refs.set(m[1], new Set());
      refs.get(m[1]).add(p.split("/ui/")[1]);
    }
  }
}
const missing = [...refs].filter(([id]) => !allDeclared.has(id));
console.log(`html 静态 id=${declared.size}，JS 内联 id=${declaredInJs.size}，并集=${allDeclared.size}`);
console.log(`ui 静态引用 id=${refs.size}，其中找不到声明=${missing.length}`);
for (const [id, fs] of missing) console.log(`  ✗ ${id}  ← ${[...fs].join(", ")}`);
