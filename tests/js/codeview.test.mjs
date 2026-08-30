// fx/codeview.js 纯函数单测（工单 code-viewer/04-05）：树构建与排序 /
// 树 HTML / 行号 gutter / 只读视图（高亮分发与转义）/ 大纲 / 搜索结果 /
// 文件内过滤。直接 import，子串断言防脆。运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import {
  buildCodeTree,
  codeTreeHTML,
  codeLineNumbersHTML,
  highlightCodeLines,
  codeViewHTML,
  outlineHTML,
  outlineEmptyHTML,
  searchListHTML,
  fileFindFilter,
} from "../../src/contest_generator/static/js/fx/codeview.js";

test("buildCodeTree：目录在前、同级码点序，路径逐层聚合", () => {
  const nodes = buildCodeTree([
    { path: "main.c", size_bytes: 10 },
    { path: "src/app.h", size_bytes: 20 },
    { path: "src/ui.h", size_bytes: 30 },
    { path: "readme.md", size_bytes: 5 },
  ]);
  assert.deepEqual(nodes.map((n) => n.name), ["src", "main.c", "readme.md"]);
  assert.deepEqual(nodes[0].children.map((c) => c.name), ["app.h", "ui.h"]);
  assert.equal(nodes[0].isDir, true);
  assert.equal(nodes[1].isDir, false);
  assert.equal(nodes[1].size_bytes, 10);
});

test("buildCodeTree：顺序无关（后端直出任意序）", () => {
  const a = buildCodeTree([
    { path: "b/x.c", size_bytes: 1 },
    { path: "a/y.c", size_bytes: 1 },
  ]);
  const b = buildCodeTree([
    { path: "a/y.c", size_bytes: 1 },
    { path: "b/x.c", size_bytes: 1 },
  ]);
  assert.deepEqual(a, b);
});

test("codeTreeHTML：目录 details/summary，文件行按钮带 data 与转义", () => {
  const nodes = buildCodeTree([
    { path: "dir/z.c", size_bytes: 1 },
    { path: "a<b.c", size_bytes: 3 },
  ]);
  const html = codeTreeHTML(nodes);
  assert.match(html, /<details open><summary>dir<\/summary>/);
  assert.match(html, /data-code-file="a&lt;b\.c"/);
  assert.ok(!html.includes("a<b.c"));
});

test("codeLineNumbersHTML：1..n 逐行 span，下限 1", () => {
  assert.equal(
    codeLineNumbersHTML(3),
    '<span class="code-gutter-line">1</span><span class="code-gutter-line">2</span>'
      + '<span class="code-gutter-line">3</span>'
  );
  assert.equal(codeLineNumbersHTML(0), '<span class="code-gutter-line">1</span>');
});

test("codeViewHTML：gutter 行数 = pre 渲染行数（尾 \n 计空行），C 高亮走单源", () => {
  const html = codeViewHTML("int x;\nvoid f() {}\n", "c");
  assert.equal((html.match(/class="code-gutter-line"/g) || []).length, 3);
  assert.match(html, /<pre class="code-pre">/);
  assert.match(html, /<span class="tok-kw">int<\/span>/);
  assert.equal((html.match(/class="code-pre-line"/g) || []).length, 3);
  assert.match(html, /data-code-line="1"/);
});

test("codeViewHTML：注入样本转义（纯文本不加高亮 span）", () => {
  const evil = codeViewHTML('<script>alert("&")</script>', "plain");
  assert.ok(!evil.includes("<script>"));
  assert.ok(evil.includes("&lt;script&gt;"));
  assert.ok(!evil.includes("tok-"));
});

test("highlightCodeLines：跨行块注释在行界闭合并按同 class 重开（视觉不变）", () => {
  const lines = highlightCodeLines("/* a\nb */\nint x;", "c");
  assert.equal(lines.length, 3);
  assert.equal((lines[0].match(/class="tok-com"/g) || []).length, 1);
  assert.equal((lines[1].match(/class="tok-com"/g) || []).length, 1);
  assert.ok(lines[0].startsWith('<span class="tok-com">'));
  assert.ok(lines[0].endsWith("</span>"));
  assert.ok(lines[1].startsWith('<span class="tok-com">'));
  assert.ok(lines[2].includes("tok-kw"));
  assert.ok(!lines[2].includes("tok-com"));
});

test("highlightCodeLines：尾 \\n 空行 / 空内容各得独立元素（与 gutter 对齐）", () => {
  assert.deepEqual(highlightCodeLines("", "c"), [""]);
  const lines = highlightCodeLines("a\n", "plain");
  assert.equal(lines.length, 2);
  assert.equal(lines[1], "");
  // 转义样本：高亮输出不回引原文
  assert.deepEqual(highlightCodeLines("<script>", "plain"), ["&lt;script&gt;"]);
});

test("outlineHTML：kind 徽标 + name + 行号；空 → 空串", () => {
  const html = outlineHTML([
    { kind: "function", name: "main", line: 3 },
    { kind: "define", name: "LED", line: 1 },
    { kind: "include", name: "app.h", line: 1 },
  ]);
  assert.match(html, /data-outline-line="3"/);
  assert.match(html, /k-function/);
  assert.match(html, />main</);
  assert.match(html, />LED</);
  assert.equal(outlineHTML([]), "");
  assert.equal(outlineHTML(null), "");
});

test("outlineEmptyHTML：中文空态文案", () => {
  assert.match(outlineEmptyHTML(), /当前文件无大纲/);
});

test("searchListHTML：命中行 + active 高亮 + 转义；空态", () => {
  const html = searchListHTML(
    [
      { path: "main.c", line: 2, text: "void helper(){}" },
      { path: "app.h", line: 5, text: "x<y" },
    ],
    "main.c"
  );
  assert.match(html, /data-search-path="main\.c" data-search-line="2"/);
  assert.match(html, /class="code-search-hit on"/);
  assert.ok(html.includes("x&lt;y"));
  assert.match(searchListHTML([], "x"), /没有命中/);
});

test("fileFindFilter：大小写不敏感子串，返回 1 基行号；空 q → []", () => {
  const lines = ["#include <stdio.h>", "int main(void) {", "return 0;", "// STDIO"];
  assert.deepEqual(fileFindFilter(lines, "stdio"), [1, 4]);
  assert.deepEqual(fileFindFilter(lines, "STDIO"), [1, 4]);
  assert.deepEqual(fileFindFilter(lines, "  "), []);
  assert.deepEqual(fileFindFilter(lines, "nope"), []);
});
