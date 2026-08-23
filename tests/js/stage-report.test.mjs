// genStageTexts / fmtWait 纯函数单测（工单 ui-polish-8/04）：
// 生成中阶段播报的子阶段文案轮播与等待计时。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
const m1 = html.match(/function genStageTexts[\s\S]*?\n\}/);
assert.ok(m1, "index.html 中未找到 genStageTexts 函数体（改名了？）");
const genStageTexts = new Function("return (" + m1[0] + ")")();
const m2 = html.match(/function fmtWait[\s\S]*?\n\}/);
assert.ok(m2, "index.html 中未找到 fmtWait 函数体（改名了？）");
const fmtWait = new Function("return (" + m2[0] + ")")();

test("genStageTexts 首阶段文案", () => {
  assert.equal(genStageTexts(0), "正在选配模块…");
});

test("genStageTexts 按序切换五个阶段", () => {
  const seq = [0, 1, 2, 3, 4].map((i) => genStageTexts(i));
  assert.deepEqual(seq, [
    "正在选配模块…",
    "正在定位母版…",
    "正在生成工程骨架…",
    "正在写入工程文件…",
    "正在生成摘要…",
  ]);
});

test("genStageTexts 越界循环回绕（正/负/小数）", () => {
  assert.equal(genStageTexts(5), "正在选配模块…");
  assert.equal(genStageTexts(7), "正在生成工程骨架…");
  assert.equal(genStageTexts(-1), "正在生成摘要…");
  assert.equal(genStageTexts(2.9), "正在生成工程骨架…");
});

test("genStageTexts 非法入参（NaN / 字符串 / null）→ 兜底首阶段", () => {
  assert.equal(genStageTexts(NaN), "正在选配模块…");
  assert.equal(genStageTexts(undefined), "正在选配模块…");
  assert.equal(genStageTexts("abc"), "正在选配模块…");
});

test("fmtWait：60 秒内 → N 秒", () => {
  assert.equal(fmtWait(0), "0 秒");
  assert.equal(fmtWait(1), "1 秒");
  assert.equal(fmtWait(59), "59 秒");
});

test("fmtWait：60 秒起 → 分秒", () => {
  assert.equal(fmtWait(60), "1 分 0 秒");
  assert.equal(fmtWait(61), "1 分 1 秒");
  assert.equal(fmtWait(125), "2 分 5 秒");
  assert.equal(fmtWait(3600), "60 分 0 秒");
});

test("fmtWait：非法入参（NaN / 负数 / 小数）", () => {
  assert.equal(fmtWait(NaN), "0 秒");
  assert.equal(fmtWait(-5), "0 秒");
  assert.equal(fmtWait(undefined), "0 秒");
  assert.equal(fmtWait("12"), "12 秒");
  assert.equal(fmtWait(2.7), "2 秒");
});
