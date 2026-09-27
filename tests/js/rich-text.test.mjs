// rich-text.test.mjs — 库数据的 markdown 粗体标记进页面怎么渲染（工单 hwcheck-hygiene/14）。
//
// 判据本体在 `fx/core.js` 的 `escRich` / `escPlain` 两个纯函数里（**单源**），本文件只测它们
// 的行为。为什么需要这一层：库数据（配方 `note.lines` 2434 处、manifest 的 `platforms.*.notes`
// 1844 处 / `description` 6 处）是按 markdown 写的，而渲染点用 `esc()` 把它们原样送进
// innerHTML——学生看到的是 `**本件必须接个已知电压才有意义**`。02 号单只扫 JS 产品串
// （判据 ⑨），库数据这一层看不见。
//
// 四条不变量（顺序与边界都是判据，不是实现细节）：
//   ① **先转义后替换**：`<script>` 之类照样是文本，替换出来的 `<strong>` 才是标签；
//   ② 成对标记 → `<strong>`；③ **孤立标记一律剥掉**（行级截断会从成对标记中间切开）；
//   ④ 属性路径（`escPlain`）只剥标记、不产生标签。
import test from "node:test";
import assert from "node:assert/strict";

import { esc, escRich, escPlain } from "../../src/contest_generator/static/js/fx/core.js";

test("escRich：成对 `**粗**` → <strong>（库数据里最常见的那一种）", () => {
  assert.equal(escRich("**本件必须接个已知电压才有意义**：ADC 读的是引脚上的电压"),
    "<strong>本件必须接个已知电压才有意义</strong>：ADC 读的是引脚上的电压");
  // 一行里两对、以及中文夹英文的混排
  assert.equal(escRich("**一件**与**另一件**"),
    "<strong>一件</strong>与<strong>另一件</strong>");
});

test("escRich：**先转义后替换** —— 库里的 <script> 仍然是文本", () => {
  const out = escRich('<img src=x onerror=alert(1)> 与 **粗**');
  assert.ok(!out.includes("<img"), "用户/库数据里的标签没被转义：" + out);
  assert.ok(out.includes("&lt;img"), out);
  assert.ok(out.includes("<strong>粗</strong>"), "成对标记该转成标签：" + out);
  // 标记**里面**的尖括号也要转义（替换发生在转义之后，不会再解释一遍）
  assert.equal(escRich("**<b>**"), "<strong>&lt;b&gt;</strong>");
});

test("escRich：孤立 / 半个标记一律剥掉（行级截断会从成对标记中间切开）", () => {
  // 截断切开的真实形态：`hwcheckOrderDesc` 60 字、模块卡简介 26 字
  assert.equal(escRich("**这里判的是「通路通不通」，不是「传感器准不准」**：读数接近 4095"),
    "<strong>这里判的是「通路通不通」，不是「传感器准不准」</strong>：读数接近 4095");
  assert.equal(escRich("**这里判的是「通路通不通」，不是「传感器准不准」"),
    "这里判的是「通路通不通」，不是「传感器准不准」");
  assert.equal(escRich("读到一半就没了**"), "读到一半就没了");
  assert.equal(escRich("****"), "");
  assert.ok(!escRich("**半截").includes("**"), "孤立标记漏到页面上了");
});

test("escPlain：属性路径只剥标记、不产生标签（标签在 title 里只会被当字面量显示）", () => {
  assert.equal(escPlain("**粗**说明"), "粗说明");
  assert.equal(escPlain("**半截"), "半截");
  assert.equal(escPlain('a "b" <c>'), "a &quot;b&quot; &lt;c&gt;");
  assert.ok(!escPlain("**粗**").includes("<strong>"), "属性路径不许出现标签");
});

test("与 esc 的关系：没有标记时逐字节等于 esc（其余渲染点不受影响）", () => {
  for (const s of ["", "普通一句", 'a "b" <c> & d', "只有 * 一个星号", "1 ** 2"]) {
    assert.equal(escRich(s), esc(s).replace(/\*\*/g, ""), `escRich 与 esc 的关系变了：${s}`);
  }
  assert.equal(escRich("普通一句"), "普通一句");
  assert.equal(escRich(null), "null", "非字符串照 esc 的口径（String()）走");
  assert.equal(escPlain(undefined), "undefined");
});
