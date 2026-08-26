// ui 模块间 import 图无环守卫（阶段 2 评审工单 21：generate-core ↔
// generate-readiness 环回归防线）。静态解析 ui/ 目录全部模块的 import 边
// （只取 ui→ui），Kahn 拓扑排序判环——违反「ui 模块之间允许单向依赖」
// （spec.md 桥接约定 3 / CONTEXT.md）时立即红。
import { readFileSync, readdirSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const UI_DIR = new URL("../../src/contest_generator/static/js/ui/", import.meta.url);
const modules = readdirSync(UI_DIR).filter((f) => f.endsWith(".js"));
const src = new Map(modules.map((f) => [f, readFileSync(new URL(f, UI_DIR), "utf8")]));

// 抓 `import { ... } from "/js/ui/xxx.js"` 与 side-effect `import "/js/ui/xxx.js"` 两类边
function edgesOf(code) {
  const out = [];
  const re = /import\s+(?:[^"'`]*?\s+from\s+)?["']\/js\/ui\/([\w.-]+\.js)["']/g;
  let m;
  while ((m = re.exec(code))) out.push(m[1]);
  return out;
}
const adj = new Map(modules.map((f) => [f, []]));
for (const [f, code] of src) {
  for (const t of edgesOf(code)) adj.get(f).push(t);
}

test("ui 模块之间 import 无环（单向依赖约定）", () => {
  const indeg = new Map([...adj].map(([n]) => [n, 0]));
  for (const [, outs] of adj) for (const t of outs) indeg.set(t, (indeg.get(t) || 0) + 1);
  const q = [...indeg].filter(([, d]) => d === 0).map(([n]) => n);
  let seen = 0;
  while (q.length) {
    const n = q.pop();
    seen++;
    for (const t of adj.get(n) || []) {
      const d = indeg.get(t) - 1;
      indeg.set(t, d);
      if (!d) q.push(t);
    }
  }
  assert.equal(seen, modules.length,
    `ui 模块存在 import 环：${[...indeg].filter(([, d]) => d > 0).map(([n]) => n).join(", ")}`);
});
