// 母版「新增平台」下拉渲染归属守卫（阶段 2 评审工单 23）：renderNewPlatformOptions
// 应定义于 ui/master.js，宿主不得内联渲染（残留 DOM 胶水回归防线）。
// 宿主 = index.html ∪ 装载根 boot.js（工单 frontend-boot-module/02 把宿主块搬去了 boot.js）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const masterSrc = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/master.js", import.meta.url), "utf8"
);
const indexSrc = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url), "utf8"
);
const bootSrc = readFileSync(
  new URL("../../src/contest_generator/static/js/boot.js", import.meta.url), "utf8"
);

test("静态断言：ui/master.js 提供并导出 renderNewPlatformOptions", () => {
  assert.match(masterSrc, /function renderNewPlatformOptions\(/, "ui/master.js 缺 renderNewPlatformOptions 定义？");
  assert.match(masterSrc, /export function renderNewPlatformOptions/, "ui/master.js 缺 renderNewPlatformOptions 导出？");
});

test("静态断言：宿主无 new-platform 内联渲染", () => {
  for (const [name, src] of [["index.html", indexSrc], ["boot.js", bootSrc]]) {
    assert.doesNotMatch(src, /\$\("new-platform"\)\.innerHTML/,
      `${name} 残留 new-platform 下拉内联渲染（工单 23 应迁 ui/master.js）`);
  }
});
