// 全局「AI 行动中」计数闸状态机 + 横幅文案单测（工单 ai-action-banner/01）。
// 语义：start 首启固定 label（并发显示最先启动的动作名）；stop 递减下限 0、
// 归零清 label；非法输入返回原 state（横幅纯观察者，绝不抛错阻断流程）。
import test from "node:test";
import assert from "node:assert/strict";
import { aiActionStep, aiActionBannerLabel } from "../../src/contest_generator/static/js/fx/ai-action.js";

const initial = { count: 0, label: "" };

test("start 首次启动固定 label", () => {
  assert.deepEqual(aiActionStep(initial, { type: "start", label: "赛题预读" }),
    { count: 1, label: "赛题预读" });
});

test("并发多 start：label 保持最先启动的，不覆盖", () => {
  let s = aiActionStep(initial, { type: "start", label: "赛题预读" });
  s = aiActionStep(s, { type: "start", label: "AI 推荐" });
  s = aiActionStep(s, { type: "start", label: "生成工程" });
  assert.deepEqual(s, { count: 3, label: "赛题预读" });
});

test("stop 递减，归零清 label", () => {
  let s = aiActionStep(initial, { type: "start", label: "赛题预读" });
  s = aiActionStep(s, { type: "stop" });
  assert.deepEqual(s, { count: 0, label: "" });
});

test("stop 溢出防护：count 下限 0，label 恒空", () => {
  let s = { count: 2, label: "赛题预读" };
  s = aiActionStep(s, { type: "stop" });
  s = aiActionStep(s, { type: "stop" });
  s = aiActionStep(s, { type: "stop" });
  assert.deepEqual(s, { count: 0, label: "" });
});

test("stop 后 label 非空时保留原 label（并发未完）", () => {
  let s = aiActionStep(initial, { type: "start", label: "赛题预读" });
  s = aiActionStep(s, { type: "start", label: "AI 推荐" });
  s = aiActionStep(s, { type: "stop" });
  assert.deepEqual(s, { count: 1, label: "赛题预读" });
});

test("start 传非字符串 label：count 为 0 时保持空标签", () => {
  assert.deepEqual(aiActionStep(initial, { type: "start", label: 42 }),
    { count: 1, label: "" });
});

test("非法 action type 原样返回", () => {
  const s = { count: 1, label: "赛题预读" };
  assert.equal(aiActionStep(s, { type: "nope" }), s);
});

test("非法 state / action 原样返回（防御式，不抛错）", () => {
  const s = { count: 1, label: "赛题预读" };
  assert.equal(aiActionStep(null, { type: "start", label: "x" }), null);
  assert.deepEqual(aiActionStep({ count: "x" }, { type: "start", label: "x" }), { count: "x" });
  assert.equal(aiActionStep(s, null), s);
  assert.equal(aiActionStep(s, "start"), s);
});

test("横幅文案：有 label 拼「AI 行动中：<label>」", () => {
  assert.equal(aiActionBannerLabel("赛题预读"), "AI 行动中：赛题预读");
});

test("横幅文案：空 label 兜底「AI 行动中…」（无冒号）", () => {
  assert.equal(aiActionBannerLabel(""), "AI 行动中…");
  assert.equal(aiActionBannerLabel(null), "AI 行动中…");
  assert.equal(aiActionBannerLabel(undefined), "AI 行动中…");
});
