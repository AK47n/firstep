// codeZoomClamp / parseZoomStored 纯函数单测（工单 code-zoom/01）：
// main.c 代码字号缩放的范围收敛与存储解析。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
const m1 = html.match(/function codeZoomClamp[\s\S]*?\n\}/);
assert.ok(m1, "index.html 中未找到 codeZoomClamp 函数体（改名了？）");
const codeZoomClamp = new Function("return (" + m1[0] + ")")();
const m2 = html.match(/function parseZoomStored[\s\S]*?\n\}/);
assert.ok(m2, "index.html 中未找到 parseZoomStored 函数体（改名了？）");
// parseZoomStored 内部调用 codeZoomClamp：分开 eval 后无共享全局，注入闭包
const parseZoomStored = new Function("codeZoomClamp", "return (" + m2[0] + ")")(codeZoomClamp);

test("clamp：正常值原样返回", () => {
  assert.equal(codeZoomClamp(100), 100);
  assert.equal(codeZoomClamp(130), 130);
});

test("clamp：小于 80 收敛到 80", () => {
  assert.equal(codeZoomClamp(79), 80);
  assert.equal(codeZoomClamp(-50), 80);
});

test("clamp：大于 200 收敛到 200", () => {
  assert.equal(codeZoomClamp(201), 200);
  assert.equal(codeZoomClamp(9999), 200);
});

test("clamp：非数值 / NaN / Infinity → 100", () => {
  assert.equal(codeZoomClamp(NaN), 100);
  assert.equal(codeZoomClamp(Infinity), 100);
  assert.equal(codeZoomClamp(-Infinity), 100);
  assert.equal(codeZoomClamp("abc"), 100);
  assert.equal(codeZoomClamp(undefined), 100);
});

test("clamp：小数四舍五入", () => {
  assert.equal(codeZoomClamp(120.4), 120);
  assert.equal(codeZoomClamp(120.6), 121);
});

test("parseZoomStored：null / 空串 / 非法文本 → 100", () => {
  assert.equal(parseZoomStored(null), 100);
  assert.equal(parseZoomStored(undefined), 100);
  assert.equal(parseZoomStored(""), 100);
  assert.equal(parseZoomStored("abc"), 100);
});

test("parseZoomStored：合法字符串解析 + 越界收敛", () => {
  assert.equal(parseZoomStored("120"), 120);
  assert.equal(parseZoomStored("999"), 200);
  assert.equal(parseZoomStored("50"), 80);
});
