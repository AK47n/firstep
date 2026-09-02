// fx/code-marks.js 选中词纯函数单测（工单 code-editor-vscode-polish/05）：
// codeWordAt（光标处词）/ codeWordRanges（同词全文区段，大小写精确 + 词边界）。
// 直接 import，子串断言防脆。运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import {
  codeWordAt,
  codeWordRanges,
} from "../../src/contest_generator/static/js/fx/code-marks.js";

test("codeWordAt：光标在词内 / 词尾紧随 → 取词", () => {
  assert.equal(codeWordAt("int main(void) {", 7), "main");   // 词内
  assert.equal(codeWordAt("int main(void) {", 8), "main");   // 词尾后（pos-1 = 最后字符）
  assert.equal(codeWordAt("abc", 0), "abc");                  // 词首
  assert.equal(codeWordAt("abc", 3), "abc");                  // 词尾后
});

test("codeWordAt：空白 / 符号 / 词间 → 空串（不误亮）", () => {
  assert.equal(codeWordAt("abc def", 3), "abc");   // pos-1 = 'c'（仍属词前词）
  assert.equal(codeWordAt("abc def", 4), "def");   // pos-1 = 空格 → 看 pos = 'd'
  assert.equal(codeWordAt("a+b", 2), "b");
  assert.equal(codeWordAt("a + b", 2), "");        // 光标在空格上
  assert.equal(codeWordAt("", 0), "");
});

test("codeWordAt：下划线与数字算词字符、中文/符号不算", () => {
  assert.equal(codeWordAt("my_var_1", 4), "my_var_1");
  assert.equal(codeWordAt("中文注释", 1), "");      // 汉字不构成词
  assert.equal(codeWordAt("x=1; y", 3), "1");      // 数字也是词字符（VSCode 同语义）
  assert.equal(codeWordAt("x = y; z", 2), "");     // '=' 符号位
});

test("codeWordRanges：大小写精确 + 词边界（_ 连接词不算同词）", () => {
  const text = "main(void) main_c main";
  assert.deepEqual(codeWordRanges(text, "main"), [
    { line: 1, start: 0, end: 4 },
    { line: 1, start: 18, end: 22 },
  ]);
  assert.deepEqual(codeWordRanges(text, "Main"), []);          // 大小写敏感
  assert.deepEqual(codeWordRanges(text, ""), []);              // 空词
});

test("codeWordRanges：多行与行边界", () => {
  const text = "main\nx main y\n";
  assert.deepEqual(codeWordRanges(text, "main"), [
    { line: 1, start: 0, end: 4 },
    { line: 2, start: 2, end: 6 },
  ]);
});
