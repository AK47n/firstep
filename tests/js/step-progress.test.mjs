// stepProgress 纯函数单测（工单 ui-polish-3/02）：顶部进度条百分比与计数文本。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
const match = html.match(/function stepProgress[\s\S]*?\n\}/);
assert.ok(match, "index.html 中未找到 stepProgress 函数体（改名了？）");
const stepProgress = new Function("return (" + match[0] + ")")();

test("0/12 → 0% 与计数文本", () => {
  assert.deepEqual(stepProgress(0, 12), { pct: 0, text: "已完成 0/12" });
});

test("12/12 → 100%", () => {
  assert.deepEqual(stepProgress(12, 12), { pct: 100, text: "已完成 12/12" });
});

test("5/12 → 42%（四舍五入）", () => {
  assert.deepEqual(stepProgress(5, 12), { pct: 42, text: "已完成 5/12" });
});

test("total 非法（0 / 负数 / NaN）→ 兜底 12", () => {
  assert.equal(stepProgress(3, 0).pct, 25);
  assert.equal(stepProgress(3, -5).pct, 25);
  assert.equal(stepProgress(3, NaN).pct, 25);
});

test("done 越界裁剪：负数 → 0，超 total → 100", () => {
  assert.equal(stepProgress(-1, 12).pct, 0);
  assert.equal(stepProgress(99, 12).pct, 100);
});

test("done 为字符串数字可解析", () => {
  assert.equal(stepProgress("6", 12).pct, 50);
});

test("done 非数字 → 0", () => {
  assert.equal(stepProgress(NaN, 12).pct, 0);
});
