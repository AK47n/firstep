// code-comment 纯函数单测（工单 code-page-vscode-overhaul/02 Ctrl+/ 注释切换）：
// toggleLineComment（C 行注释 // 逐行；XML <!-- --> 逐行）与
// toggleBlockComment（/* */ 加/去包围）——基于 {value, selStart, selEnd} 纯
// 输入输出，期望值全部手工推算。
import test from "node:test";
import assert from "node:assert/strict";
import {
  toggleLineComment,
  toggleBlockComment,
} from "../../src/contest_generator/static/js/fx/code-comment.js";

// ---- toggleLineComment：逐行切换（C：//）----

test("C 单行加注释（光标在行中）：注释前缀后光标随行", () => {
  const r = toggleLineComment("int x;", 3, 3, { open: "//" });
  assert.deepEqual(r, { value: "// int x;", start: 6, end: 6 });
});

test("C 单行去注释（光标在行中）：前缀移除光标回原列", () => {
  const r = toggleLineComment("// int x;", 6, 6, { open: "//" });
  assert.deepEqual(r, { value: "int x;", start: 3, end: 3 });
});

test("C 多行逐行加注释：选区扩展为整段", () => {
  const r = toggleLineComment("int a;\nint b;", 0, 7, { open: "//" });
  assert.deepEqual(r, { value: "// int a;\n// int b;", start: 0, end: 19 });
});

test("C 空行跳过：空白行不注释", () => {
  const r = toggleLineComment("a\n\nb", 0, 4, { open: "//" });
  assert.deepEqual(r, { value: "// a\n\n// b", start: 0, end: 10 });
});

test("C 多行已注释：全部去注释", () => {
  const r = toggleLineComment("// a\n// b", 0, 8, { open: "//" });
  assert.deepEqual(r, { value: "a\nb", start: 0, end: 3 });
});

test("C 缩进保留：注释插在前导空白之后", () => {
  const r = toggleLineComment("    int x;", 10, 10, { open: "//" });
  assert.deepEqual(r, { value: "    // int x;", start: 13, end: 13 });
});

test("纯空白行选区：no-op", () => {
  const r = toggleLineComment("   \n", 0, 3, { open: "//" });
  assert.deepEqual(r, { value: "   \n", start: 0, end: 3 });
});

// ---- toggleLineComment：XML（<!-- --> 逐行）----

test("XML 单行加注释：<!-- 内容 -->", () => {
  const r = toggleLineComment("<a>x</a>", 0, 9, { open: "<!--", close: "-->" });
  assert.deepEqual(r, { value: "<!-- <a>x</a> -->", start: 0, end: 17 });
});

test("XML 单行去注释：剥掉 <!-- 与 -->（含配对空格）", () => {
  const r = toggleLineComment("<!-- <a>x</a> -->", 0, 18, { open: "<!--", close: "-->" });
  assert.deepEqual(r, { value: "<a>x</a>", start: 0, end: 8 });
});

// ---- toggleBlockComment：/* */ 加/去包围 ----

test("块注释加：无块标记选区整体包围", () => {
  const r = toggleBlockComment("int x;\nint y;", 0, 14, { open: "/*", close: "*/" });
  assert.deepEqual(r, { value: "/*int x;\nint y;*/", start: 0, end: 17 });
});

test("块注释去：精确块注释解除包围", () => {
  const r = toggleBlockComment("/*int x;\nint y;*/", 0, 18, { open: "/*", close: "*/" });
  assert.deepEqual(r, { value: "int x;\nint y;", start: 0, end: 13 });
});

test("块注释去：混合选区含块 → 解除最外层包围", () => {
  const r = toggleBlockComment("x = 1;\n/* note */\ny = 2;", 0, 24, { open: "/*", close: "*/" });
  assert.deepEqual(r, { value: "x = 1;\n note \ny = 2;", start: 0, end: 20 });
});
