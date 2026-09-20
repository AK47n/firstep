import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("../../src/contest_generator/static/js/", import.meta.url);
const files = [];
for (const dir of [".", "fx", "ui"]) {
  for (const name of readdirSync(new URL(dir === "." ? "./" : dir + "/", ROOT))) {
    if (name.endsWith(".js")) files.push({ dir, name, path: new URL(dir === "." ? name : `${dir}/${name}`, ROOT) });
  }
}
const sources = new Map(files.map((f) => [f.name, readFileSync(f.path, "utf8")]));

// 22 个被删掉 index.html 装载的 fx 模块
const DROPPED = ["core", "env", "btn-icon", "platform", "code", "pdf", "reference", "topic", "master",
  "module", "overview", "draft", "wait", "generate", "recent", "codeview", "readiness", "llm",
  "score", "task", "settings", "workflow"];

const html = readFileSync(new URL("../index.html", ROOT), "utf8");
// 只认 **import 语句**里的说明符（注释里的墓碑记录不算装载）
const htmlImports = new Set(
  [...html.matchAll(/^[ \t]*import\s*(?:\{[^}]*\}\s*from\s*)?["']([^"']+)["']/gm)].map((m) => m[1])
);
console.log(`扫了 ${files.length} 个模块（js/ 根 + fx/ + ui/）；index.html 现有装载 ${htmlImports.size} 条`);
console.log("被删装载的 fx 模块 → 仍被谁 import（不含 index.html 的装载）");
let orphans = [];
for (const slug of DROPPED) {
  const spec = `/js/fx/${slug}.js`;
  const importers = [];
  for (const [name, src] of sources) {
    const re = new RegExp(`from\\s+["'][^"']*\\/fx\\/${slug}\\.js["']|from\\s+["']\\.\\/${slug}\\.js["']`, "g");
    if (re.test(src)) importers.push(name);
  }
  console.log(`  fx/${slug}.js  ← ${importers.length} 个模块${htmlImports.has(spec) ? "（index.html 仍有具名装载）" : ""}  ${importers.slice(0, 6).join(", ")}${importers.length > 6 ? " …" : ""}`);
  if (importers.length === 0) orphans.push(slug);
}
console.log(orphans.length ? `\n⚠ 变成孤岛的 fx 模块: ${orphans.join(", ")}` : "\n✓ 22 个 fx 模块全部仍被模块图引用（无孤岛）");
