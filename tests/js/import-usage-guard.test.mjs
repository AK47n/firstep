// import-usage-guard.test.mjs — 装载清单不变量（工单 frontend-import-fossils/01；
// 工单 frontend-boot-module/02 重定根到 static/js/boot.js）。
//
// 这张前端模块图的**唯一装载点**是手写的：69 条 import 里曾有 259 个名字宿主正文一次都
// 没用过（纯函数迁 fx/ 与 tab 迁 ui/ 两轮模块化留下的冻结产物）。代价不是"多几行"，
// 而是**全局失败模式**：删/改其中任一导出，浏览器解析 import 就抛 SyntaxError，
// 整页脚本全灭（2026-09-12 真机现场，服务端全 200）。
//
// 本文件把不变量钉住：**页面不许导入它不使用的名字**。清单从 index.html 搬进 boot.js 之后
// （工单 02），取数面跟着搬家——判据本体一字未改；"零裸装载"那一条随工单 03 落地
// （那时清单里才真的没有裸装载）。
//
// 判据本体在 tests/js/import-usage.mjs（单源；红证脚本也 import 它）。与既有守卫的分工：
//   static-import-guard.test.mjs  装载根清单 ↔ 模块导出对账 + index.html 零 import
//   boot-contract.mjs 的判据        index.html 零定义 / 零裸装载 / 接线不住求值期 / 全图对账
//   本文件                          装载根导入的名字必须真的被用（防化石回流）
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { parseImports, unusedImports } from "./import-usage.mjs";
import { readLoadRoot, bareLoads } from "./boot-contract.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const ROOT = readLoadRoot(STATIC);
assert.ok(ROOT !== null, "找不到装载根 static/js/boot.js");
const IMPORTS = parseImports(ROOT);

test("抽取器不静默失效：装载清单抽得到、且每条都指向 /js/ 下的模块", () => {
  assert.ok(IMPORTS.length >= 40, `只抽到 ${IMPORTS.length} 条 import（boot.js 结构变了？）`);
  const bad = IMPORTS.filter((i) => !i.spec.startsWith("/js/")).map((i) => i.spec);
  assert.deepEqual(bad, [], `装载清单里出现非 /js/ 说明符：${bad.join(", ")}`);
  const names = IMPORTS.reduce((n, i) => n + i.names.length, 0);
  assert.ok(names >= 50, `具名导入只抽到 ${names} 个（抽取器或清单形态变了）`);
});

test("装载根不许导入它不使用的名字（零化石）", () => {
  const problems = unusedImports(ROOT).map(({ spec, unused }) => `${spec}: ${unused.join(", ")}`);
  assert.deepEqual(
    problems,
    [],
    "装载清单里有宿主用不到的名字 —— 它们不干活，但改名/删除会让整页 SyntaxError。\n"
      + "要么删掉这个名字，要么把它接进显式的 init 调用：\n"
      + problems.join("\n")
  );
});

test("具名清单非空且无重复名（防 `import {} from` 与重复登记）", () => {
  for (const { spec, names, raw } of IMPORTS) {
    if (!/^[ \t]*import\s*\{/.test(raw)) continue; // 裸 import 归末尾那条「零裸装载」判
    assert.ok(names.length > 0, `${spec} 写成空具名清单`);
    assert.equal(new Set(names).size, names.length, `${spec} 的具名清单里有重复名字`);
  }
});

test("装载根零裸装载（\"靠被加载才接线\"这条隐式边已退场，不许回潮）", () => {
  const bare = bareLoads(ROOT).map((b) => `  ${b.line}: import "${b.spec}"`);
  assert.deepEqual(
    bare,
    [],
    "装载清单里出现裸装载（import \"…\"）—— 那是「这个模块靠被加载才生效」的隐式边：\n"
      + "接线要写成模块导出的 init*()，再由装载根显式调用：\n" + bare.join("\n")
  );
});
