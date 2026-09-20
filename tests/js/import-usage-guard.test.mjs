// import-usage-guard.test.mjs — 页面装载清单不变量（工单 frontend-import-fossils/01）：
//
// index.html 的 `<script type="module">` 是这张前端模块图的**唯一装载点**，而它是手写的：
// 69 条 import 里曾有 259 个名字宿主正文一次都没用过（纯函数迁 fx/ 与 tab 迁 ui/ 两轮
// 模块化留下的冻结产物）。代价不是"多几行"，而是**全局失败模式**：删/改其中任一导出，
// 浏览器解析 import 就抛 SyntaxError，整页脚本全灭（2026-09-12 真机现场，服务端全 200）。
//
// 本文件把不变量钉住：**页面不许导入它不使用的名字**；零具名使用的装载必须写成裸 import
// （`import "/js/ui/x.js"`）——后者是"靠被加载才接线"的显式声明，不是未使用名字的垃圾桶。
//
// 判据本体在 tests/js/import-usage.mjs（单源；红证脚本也 import 它）。与既有两条守卫的分工：
//   static-import-guard.test.mjs  抽 import ↔ 模块导出对账（防死导入打崩整页）+
//                                 每条装载指向的文件真实存在
//   fx-guard.test.mjs             已搬名字单源在模块、index.html 无定义（防双源回退）
//   本文件                          导入的名字必须真的被用（防化石回流）
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { hostScript, parseImports, unusedImports } from "./import-usage.mjs";

const STATIC = new URL("../../src/contest_generator/static/", import.meta.url);
const html = readFileSync(new URL("index.html", STATIC), "utf8");
const SCRIPT = hostScript(html);
const IMPORTS = parseImports(SCRIPT);

test("抽取器不静默失效：装载清单抽得到、且每条都指向 /js/ 下的模块", () => {
  assert.ok(IMPORTS.length >= 40, `只抽到 ${IMPORTS.length} 条 import（index.html 结构变了？）`);
  const bad = IMPORTS.filter((i) => !i.spec.startsWith("/js/")).map((i) => i.spec);
  assert.deepEqual(bad, [], `装载清单里出现非 /js/ 说明符：${bad.join(", ")}`);
  const names = IMPORTS.reduce((n, i) => n + i.names.length, 0);
  assert.ok(names >= 50, `具名导入只抽到 ${names} 个（抽取器或清单形态变了）`);
});

test("页面不许导入它不使用的名字（零化石）", () => {
  const problems = unusedImports(SCRIPT).map(({ spec, unused }) => `${spec}: ${unused.join(", ")}`);
  assert.deepEqual(
    problems,
    [],
    "装载清单里有宿主用不到的名字 —— 它们不干活，但改名/删除会让整页 SyntaxError。\n" +
      "要么删掉这个名字，要么（若该模块靠被加载才接线）改成裸 import：\n" +
      problems.join("\n")
  );
});

test("具名清单非空且无重复名（防 `import {} from` 与重复登记）", () => {
  for (const { spec, names, raw } of IMPORTS) {
    if (!/^[ \t]*import\s*\{/.test(raw)) continue; // 裸 import 合法
    assert.ok(names.length > 0, `${spec} 写成空具名清单 —— 要裸装载请写 import "${spec}"`);
    assert.equal(new Set(names).size, names.length, `${spec} 的具名清单里有重复名字`);
  }
});
