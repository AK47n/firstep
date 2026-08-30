// tests/js/glossary.test.mjs — 新手词表纯函数（newcomer-glossary/01）：
// 词条数据（14 词定稿，spec「词表数据」逐字；beginner-guide-enrich/04
// 增「评分点」「参数速调」；beginner-gap-closure/03 增「TODO」「增量」）
// + glossaryHTML() 渲染结构、默认收起（无 open）、term 加粗、HTML 转义。
// 仿 welcome.test.mjs 先例（node:test + assert/strict，无 DOM 依赖）。
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
];

test("GLOSSARY_TERMS：14 词定稿（term 顺序与 spec 一致）", () => {
  assert.equal(GLOSSARY_TERMS.length, 14);
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

test("glossaryHTML：默认渲染 14 个词条", () => {
  const html = glossaryHTML();
  const count = (html.match(/class="glossary-item"/g) || []).length;
  assert.equal(count, 14);
});

test("glossaryHTML：14 词全部渲染（term 加粗 + plain 直述）", () => {
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
