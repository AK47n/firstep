// tests/js/glossary.test.mjs — 新手词表纯函数（newcomer-glossary/01）：
// 词条数据（19 词：14 词定稿 + 工单 ux-walkthrough-02/18 增 自备/词表/重推/
// 选型/补问）+ glossaryHTML() 渲染结构、默认收起（无 open）、term 加粗、
// HTML 转义。仿 welcome.test.mjs 先例（node:test + assert/strict，无 DOM）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  GLOSSARY_TERMS,
  glossaryHTML,
} from "../../src/contest_generator/static/js/fx/glossary.js";

const TERM_ORDER = [
  "母版", "模块", "多实例", "平台警告", "收敛循环",
  "库外建议", "引脚角色", "骨架", "任务推进", "交接提示词",
  "评分点", "参数速调", "TODO", "增量",
  "自备", "词表（硬件词表）", "重推", "选型（买件商量）", "补问",
];

test("GLOSSARY_TERMS：19 词定稿（term 顺序与 spec 一致）", () => {
  assert.equal(GLOSSARY_TERMS.length, 19);
  assert.deepEqual(GLOSSARY_TERMS.map((t) => t.term), TERM_ORDER);
});

test("GLOSSARY_TERMS：每条 term/plain 非空且 plain 含中文", () => {
  for (const t of GLOSSARY_TERMS) {
    assert.ok(t.term && t.term.trim().length > 0, `term 为空：${t.term}`);
    assert.ok(t.plain && t.plain.trim().length > 0, `plain 为空：${t.term}`);
    assert.match(t.plain, /[\u4e00-\u9fff]/, `plain 无中文：${t.term}`);
  }
});

test("glossaryHTML：details 结构 + summary 文案 + 默认收起（无 open）", () => {
  const html = glossaryHTML();
  assert.match(html, /^<details class="card-details">/);
  assert.match(html, /<summary>新手词表/);
  assert.match(html, /<div class="card-details-body">/);
  assert.doesNotMatch(html, /<details[^>]*\sopen(\s|>)/);
});

test("glossaryHTML：默认渲染 19 个词条", () => {
  const html = glossaryHTML();
  const count = (html.match(/class="glossary-item"/g) || []).length;
  assert.equal(count, 19);
});

test("glossaryHTML：19 词全部渲染（term 加粗 + plain 直述）", () => {
  const html = glossaryHTML();
  for (const t of GLOSSARY_TERMS) {
    assert.ok(
      html.includes("<b>" + t.term + "</b>：" + t.plain),
      `词条未渲染：${t.term}`
    );
  }
});

test("glossaryHTML：HTML 特殊字符被转义（不直出）", () => {
  const html = glossaryHTML([{ term: "a<b", plain: "c&d" }]);
  assert.ok(html.includes("a&lt;b"));
  assert.ok(html.includes("c&amp;d"));
  assert.ok(!html.includes("a<b"));
  assert.ok(!html.includes("c&d"));
});
