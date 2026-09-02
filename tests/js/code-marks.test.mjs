// fx/code-marks.js 纯函数单测（工单 code-editor-vscode-polish/04/05/06）：
// 查找命中区段 / 标记层 HTML（含优先级与转义）。直接 import，子串断言防脆。
// 运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import {
  codeFindRanges,
  codeMarksHTML,
} from "../../src/contest_generator/static/js/fx/code-marks.js";

test("codeFindRanges：大小写不敏感、多行、1 基行号与 0 基列偏移", () => {
  const text = "Foo\nbarfoo\nFOO!\n";
  assert.deepEqual(codeFindRanges(text, "foo"), [
    { line: 1, start: 0, end: 3 },
    { line: 2, start: 3, end: 6 },
    { line: 3, start: 0, end: 3 },
  ]);
});

test("codeFindRanges：空针 / 无匹配 / 非重叠（向前推进避免重叠命中）", () => {
  assert.deepEqual(codeFindRanges("abc", ""), []);
  assert.deepEqual(codeFindRanges("abc", " "), []);          // 空白 trim 后为空
  assert.deepEqual(codeFindRanges("abc", "z"), []);
  assert.deepEqual(codeFindRanges("aaa", "aa"), [{ line: 1, start: 0, end: 2 }]);
  assert.deepEqual(codeFindRanges("aXaXa", "aX"), [
    { line: 1, start: 0, end: 2 },
    { line: 1, start: 2, end: 4 },
  ]);
});

test("codeFindRanges：查询 trim（与 fileFindFilter 列表一致——评审整改 04）", () => {
  assert.deepEqual(codeFindRanges("abc abc", " abc "), [
    { line: 1, start: 0, end: 3 },
    { line: 1, start: 4, end: 7 },
  ]);
});

test("codeFindRanges：跨行不匹配（按行边界切分）", () => {
  // "foo\nbar" 中不跨行匹配 "o\nb"
  assert.deepEqual(codeFindRanges("foo\nbar", "o\nb"), []);
});

test("codeMarksHTML：逐行 span + 命中类 + 转义（< & 全 &lt;）", () => {
  const html = codeMarksHTML("ab<cd\nbx", [
    { line: 1, start: 2, end: 5, kind: "hit" },
  ]);
  assert.match(html, /data-code-line="1"/);
  assert.match(html, /data-code-line="2"/);
  assert.match(html, /class="code-mark code-mark-hit"/);
  assert.match(html, /&lt;cd/);           // 转义
  assert.ok(!html.includes("ab<cd"));
});

test("codeMarksHTML：当前命中优先类 + 行数含尾空行", () => {
  const html = codeMarksHTML("abc\n", [
    { line: 1, start: 0, end: 3, kind: "hit" },
    { line: 1, start: 0, end: 3, kind: "current" },
  ]);
  assert.match(html, /code-mark-current/);
  assert.match(html, /data-code-line="2"/);   // 尾 \n 空行也渲染
});

test("codeMarksHTML：无标记 → 纯文本行（无 mark span 类）", () => {
  const html = codeMarksHTML("abc", []);
  assert.match(html, /data-code-line="1"/);
  assert.ok(!html.includes('class="code-mark '));   // 无命中/词/括号 span
});

test("codeMarksHTML：选中词 / 括号配对类渲染（透明层仅背景）", () => {
  const html = codeMarksHTML("int main(void) {", [
    { line: 1, start: 13, end: 15, kind: "word" },
  ]);
  assert.match(html, /code-mark-word/);
});
