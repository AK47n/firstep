// code-lineops 纯函数单测（工单 code-page-vscode-overhaul/01 行操作与反缩进）：
// shiftTab / deleteLine / moveLine / copyLine / lineRangeOf——全部基于
// {text, selStart, selEnd} 纯输入输出，不依赖 DOM。
import test from "node:test";
import assert from "node:assert/strict";
import {
  shiftTab,
  deleteLine,
  moveLine,
  copyLine,
  lineRangeOf,
} from "../../src/contest_generator/static/js/fx/code-lineops.js";

// ---- shiftTab：反缩进（与 indentLines 对称，4 空格 / 单个 tab 为一档）----

test("shiftTab 多行选区：每行去 4 空格，选区覆盖整段", () => {
  const r = shiftTab("    a\n      b\nc", 0, 14);
  assert.deepEqual(r, { value: "a\n  b\nc", start: 0, end: 5 });
});

test("shiftTab 单行光标在缩进内：光标钳回行首", () => {
  const r = shiftTab("    abc", 2, 2);
  assert.deepEqual(r, { value: "abc", start: 0, end: 0 });
});

test("shiftTab 单行光标在行尾：光标随缩进左移", () => {
  const r = shiftTab("    abc", 7, 7);
  assert.deepEqual(r, { value: "abc", start: 3, end: 3 });
});

test("shiftTab 前导单个 tab：去一档", () => {
  const r = shiftTab("\tfoo", 4, 4);
  assert.deepEqual(r, { value: "foo", start: 3, end: 3 });
});

test("shiftTab 无前导空白：原样返回", () => {
  const r = shiftTab("abc\n", 1, 1);
  assert.deepEqual(r, { value: "abc\n", start: 1, end: 1 });
});

// ---- deleteLine：删除选中触及的完整行（含行尾换行）----

test("deleteLine 删除中间行（带行尾换行）", () => {
  const r = deleteLine("a\nb\nc", 2, 2);
  assert.deepEqual(r, { value: "a\nc", start: 2, end: 2 });
});

test("deleteLine 删除末行（无尾换行）：连同其前换行", () => {
  const r = deleteLine("abc\ndef", 4, 4);
  assert.deepEqual(r, { value: "abc", start: 3, end: 3 });
});

test("deleteLine 删除末行（文档以换行结尾）：保留尾换行", () => {
  const r = deleteLine("a\nb\n", 2, 2);
  assert.deepEqual(r, { value: "a\n", start: 2, end: 2 });
});

test("deleteLine 选中全部：清空", () => {
  const r = deleteLine("a\nb", 0, 4);
  assert.deepEqual(r, { value: "", start: 0, end: 0 });
});

test("deleteLine 多行选区：整段删除", () => {
  const r = deleteLine("abc\ndef\nghi", 1, 8);
  assert.deepEqual(r, { value: "ghi", start: 0, end: 0 });
});

// ---- moveLine：Alt+↑/↓ 移动整行（选区跟随块）----

test("moveLine 下移单行：光标随行移动", () => {
  const r = moveLine("a\nb\nc", 0, 0, "down");
  assert.deepEqual(r, { value: "b\na\nc", start: 2, end: 2 });
});

test("moveLine 上移单行：光标随行移动", () => {
  const r = moveLine("a\nb\nc", 2, 2, "up");
  assert.deepEqual(r, { value: "b\na\nc", start: 0, end: 0 });
});

test("moveLine 首行上移：no-op", () => {
  const r = moveLine("a\nb", 0, 0, "up");
  assert.deepEqual(r, { value: "a\nb", start: 0, end: 0 });
});

test("moveLine 末行下移：no-op", () => {
  const r = moveLine("a\nb", 3, 3, "down");
  assert.deepEqual(r, { value: "a\nb", start: 3, end: 3 });
});

test("moveLine 多行块下移：选区跟随块（含行尾换行）", () => {
  const r = moveLine("a\nb\nc\nd", 0, 4, "down");
  assert.deepEqual(r, { value: "c\na\nb\nd", start: 2, end: 6 });
});

test("moveLine 多行块上移：选区跟随块（含行尾换行）", () => {
  const r = moveLine("a\nb\nc\nd", 4, 8, "up");
  assert.deepEqual(r, { value: "a\nc\nd\nb", start: 2, end: 6 });
});

test("moveLine 光标在行首（零长选区）上移：留在行首", () => {
  const r = moveLine("a\nb\nc", 2, 2, "up");
  assert.deepEqual(r, { value: "b\na\nc", start: 0, end: 0 });
});

// ---- copyLine：Shift+Alt+↑/↓ 复制行（光标落副本）----

test("copyLine 下复制单行：光标落副本", () => {
  const r = copyLine("a\nb", 2, 2, "down");
  assert.deepEqual(r, { value: "a\nb\nb", start: 4, end: 4 });
});

test("copyLine 上复制单行：光标落副本", () => {
  const r = copyLine("a\nb", 2, 2, "up");
  assert.deepEqual(r, { value: "a\nb\nb", start: 2, end: 2 });
});

test("copyLine 下复制多行块：选区移副本", () => {
  const r = copyLine("a\nb\nc", 0, 4, "down");
  assert.deepEqual(r, { value: "a\nb\na\nb\nc", start: 4, end: 8 });
});

// ---- lineRangeOf：Ctrl+L 选整行（含行尾换行；重复按扩展）----

test("lineRangeOf 单行：含行尾换行", () => {
  const r = lineRangeOf("abc\ndef\nghi", 1, 2);
  assert.deepEqual(r, { start: 0, end: 4 });
});

test("lineRangeOf 末行（无换行）：到文末", () => {
  const r = lineRangeOf("abc\ndef", 5, 5);
  assert.deepEqual(r, { start: 4, end: 7 });
});

test("lineRangeOf 选区含行尾换行：扩展到下一行", () => {
  const r = lineRangeOf("abc\ndef\nghi", 0, 4);
  assert.deepEqual(r, { start: 0, end: 8 });
});

test("lineRangeOf 多行选区：整段（含末行换行）", () => {
  const r = lineRangeOf("abc\ndef\nghi", 1, 6);
  assert.deepEqual(r, { start: 0, end: 8 });
});

test("lineRangeOf 零长选区在行中：选当前行", () => {
  const r = lineRangeOf("abc\ndef\nghi", 5, 5);
  assert.deepEqual(r, { start: 4, end: 8 });
});
