// 编译错误行 → main.c 预览定位纯函数单测（工单 compile-error-jump/01）：
// maincLineOffsetRange（行号 → 字符偏移区间）与 isMainCPath（路径判定）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
const m1 = html.match(/function maincLineOffsetRange[\s\S]*?\n\}/);
assert.ok(m1, "index.html 中未找到 maincLineOffsetRange 函数体（改名了？）");
const maincLineOffsetRange = new Function("return (" + m1[0] + ")")();
const m2 = html.match(/function isMainCPath[\s\S]*?\n\}/);
assert.ok(m2, "index.html 中未找到 isMainCPath 函数体（改名了？）");
const isMainCPath = new Function("return (" + m2[0] + ")")();

test("偏移：多行文本按 \\n 前缀和定位", () => {
  const text = "int a;\nint b;\nint c;\n";
  assert.deepEqual(maincLineOffsetRange(text, 1), { start: 0, end: 6 });
  assert.deepEqual(maincLineOffsetRange(text, 2), { start: 7, end: 13 });
  assert.deepEqual(maincLineOffsetRange(text, 3), { start: 14, end: 20 });
});

test("偏移：末行无换行符也命中", () => {
  assert.deepEqual(maincLineOffsetRange("aa\nbb", 2), { start: 3, end: 5 });
});

test("偏移：超长行（折行不影响偏移——逻辑行与视觉折行无关）", () => {
  const long = "x".repeat(300);
  const text = long + "\nabc\n";
  assert.deepEqual(maincLineOffsetRange(text, 2), { start: 301, end: 304 });
});

test("偏移：空行首尾同点", () => {
  assert.deepEqual(maincLineOffsetRange("aa\n\nbb", 2), { start: 3, end: 3 });
});

test("偏移：\\r\\n 时 \\r 计入行尾长度（与 textarea 值一致）", () => {
  const text = "aa\r\nbb\r\n";
  assert.deepEqual(maincLineOffsetRange(text, 1), { start: 0, end: 3 });
  assert.deepEqual(maincLineOffsetRange(text, 2), { start: 4, end: 7 });
});

test("偏移：越界 / 非法行号 → null（防御，不抛）", () => {
  assert.equal(maincLineOffsetRange("aa\nbb", 0), null);
  assert.equal(maincLineOffsetRange("aa\nbb", 3), null);
  assert.equal(maincLineOffsetRange("aa\nbb", 1.5), null);
  assert.equal(maincLineOffsetRange("aa\nbb", "x"), null);
  // null / 空文本防御：按空串（1 个空行，首尾同点；textarea.value 永不为 null）
  assert.deepEqual(maincLineOffsetRange(null, 1), { start: 0, end: 0 });
  assert.deepEqual(maincLineOffsetRange("", 1), { start: 0, end: 0 });
});

test("路径判定：各形态 main.c 命中", () => {
  assert.equal(isMainCPath("main.c"), true);
  assert.equal(isMainCPath("./main.c"), true);
  assert.equal(isMainCPath("../src/main.c"), true);
  assert.equal(isMainCPath("C:\\proj\\main.c"), true);
  assert.equal(isMainCPath("/abs/path/main.c"), true);
});

test("路径判定：非 main.c / 空值不命中", () => {
  assert.equal(isMainCPath("isr.c"), false);
  assert.equal(isMainCPath("modules/led/code/led.c"), false);
  assert.equal(isMainCPath("main.c.bak"), false);
  assert.equal(isMainCPath(""), false);
  assert.equal(isMainCPath(null), false);
});
