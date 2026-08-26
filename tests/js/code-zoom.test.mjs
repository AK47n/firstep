// codeZoomClamp / parseZoomStored 纯函数单测（工单 code-zoom/01）：
// main.c 代码字号缩放的范围收敛与存储解析。
import test from "node:test";
import assert from "node:assert/strict";
import { codeZoomClamp, parseZoomStored } from "../../src/contest_generator/static/js/fx/code.js";

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
