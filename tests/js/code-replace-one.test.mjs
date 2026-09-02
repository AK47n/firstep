// replaceOneAt 纯函数单测（工单 code-page-vscode-overhaul/03 查找替换增强）：
// 替换当前命中（与 codeFindRanges 同语义：大小写不敏感、非重叠、不跨行、
// 查询 trim），返回下一命中位置（替换点之后首个，不环绕）。
import test from "node:test";
import assert from "node:assert/strict";
import { replaceOneAt } from "../../src/contest_generator/static/js/fx/codeeditor.js";

test("替换当前命中：返回新文本与下一命中位置", () => {
  const r = replaceOneAt("a = 1; a = 2;", "a", "bb", 0);
  assert.equal(r.replaced, true);
  assert.equal(r.value, "bb = 1; a = 2;");
  assert.deepEqual(r.next, { line: 1, start: 8, end: 9 });
  assert.equal(r.total, 1);
});

test("替换最后一个命中：无下一处（不环绕）", () => {
  const r = replaceOneAt("a b a", "a", "c", 1);
  assert.equal(r.replaced, true);
  assert.equal(r.value, "a b c");
  assert.equal(r.next, null);
  assert.equal(r.total, 1);
});

test("大小写不敏感：替换原字符（保留原文大小写）", () => {
  const r = replaceOneAt("Aa", "a", "x", 0);
  assert.equal(r.value, "xa");
  assert.deepEqual(r.next, { line: 1, start: 1, end: 2 });
});

test("命中索引越界：不替换", () => {
  const r = replaceOneAt("a b", "a", "x", 3);
  assert.equal(r.replaced, false);
  assert.equal(r.value, "a b");
  assert.equal(r.total, 1);
});

test("空查询：不替换", () => {
  const r = replaceOneAt("a b", "  ", "x", 0);
  assert.equal(r.replaced, false);
  assert.equal(r.value, "a b");
  assert.equal(r.total, 0);
});

test("多行命中：返回下一处（行号正确）", () => {
  const r = replaceOneAt("a\nb\na", "a", "z", 0);
  assert.equal(r.value, "z\nb\na");
  assert.deepEqual(r.next, { line: 3, start: 0, end: 1 });
  assert.equal(r.total, 1);
});
