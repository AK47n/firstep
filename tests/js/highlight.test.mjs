// fx/highlight.js 纯函数单测（工单 master-library-ui-2/03）：语言判定 /
// XML 高亮 / 分发与超限回退。直接 import，子串断言防脆。
import test from "node:test";
import assert from "node:assert/strict";
import {
  languageOf,
  highlightXml,
  highlightText,
  HIGHLIGHT_MAX_BYTES,
} from "../../src/contest_generator/static/js/fx/highlight.js";

test("languageOf：.c/.h → c；.syscfg/.uvprojx/.cproject/.xml → xml；其余 plain", () => {
  assert.equal(languageOf("main.c"), "c");
  assert.equal(languageOf("user/oled.h"), "c");
  assert.equal(languageOf("MAIN.C"), "c"); // 大小写不敏感
  assert.equal(languageOf("mspm0.syscfg"), "xml");
  assert.equal(languageOf("user/Project.uvprojx"), "xml");
  assert.equal(languageOf(".cproject"), "xml");
  assert.equal(languageOf("design.xml"), "xml");
  assert.equal(languageOf("readme.txt"), "plain");
  assert.equal(languageOf("no-ext"), "plain");
  assert.equal(languageOf(""), "plain");
});

test("highlightXml：注释/声明/PI/标签/属性/引号值分类", () => {
  const out = highlightXml('<?xml version="1.0"?>\n<!-- 注 -->\n<Root a="1" b=\'2\'>\n  <Child/>\n</Root>');
  assert.match(out, /<span class="tok-pre">&lt;\?xml version=&quot;1\.0&quot;\?&gt;<\/span>/);
  assert.match(out, /<span class="tok-com">&lt;!-- 注 --&gt;<\/span>/);
  assert.match(out, /<span class="tok-tag">&lt;Root<\/span>/);
  assert.match(out, /<span class="tok-attr">a<\/span/);
  assert.match(out, /<span class="tok-val">&quot;1&quot;<\/span>/);
  assert.match(out, /<span class="tok-val">&#39;2&#39;<\/span>/);
  assert.match(out, /<span class="tok-tag">&lt;\/Root&gt;<\/span>/);
});

test("highlightXml：CDATA 与 DOCTYPE 落入预定义类", () => {
  const out = highlightXml('<!DOCTYPE root [<!ELEMENT root EMPTY>]>\n<![CDATA[raw <b>]]>');
  assert.match(out, /<span class="tok-pre">/);
  assert.match(out, /<span class="tok-str">&lt;!\[CDATA\[raw &lt;b&gt;\]\]&gt;<\/span>/);
});

test("highlightXml：注入样本转义（无裸 <script> 与 &）", () => {
  const out = highlightXml('<a href="x"><script>alert("&")</script></a>');
  assert.ok(!out.includes("<script>"));
  assert.ok(out.includes("&lt;script"));
  assert.ok(out.includes("&amp;"));
});

test("highlightText：C 分发到 cHighlight（tok-kw），plain 纯转义无高亮", () => {
  const c = highlightText("int x = 1;", "c");
  assert.match(c, /<span class="tok-kw">int<\/span>/);
  const plain = highlightText("a < b && c", "plain");
  assert.ok(plain.includes("&lt;"));
  assert.ok(!plain.includes("tok-"));
  const xml = highlightText("<a b='1'>", "xml");
  assert.match(xml, /<span class="tok-tag">&lt;a<\/span>/);
});

test("highlightText：超过 HIGHLIGHT_MAX_BYTES 回退纯文本（无高亮 span）", () => {
  const big = "0123456789abcdef".repeat(HIGHLIGHT_MAX_BYTES / 16 + 1);
  assert.ok(big.length > HIGHLIGHT_MAX_BYTES);
  const out = highlightText(big, "c");
  assert.ok(!out.includes("tok-"));
  assert.ok(out.includes("0123456789abcdef"));
});
