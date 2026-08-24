// 步骤 2 / 4 完成判定单测（本轮修复：两步骤此前从未有过 markStepDone 调用）。
// syncStep4 为纯判定（注入 stub markStepDone / markStepUndone 与两个 id 数组）；
// 另加静态断言防回归：简介成功回调必须含 markStepDone(2)。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
const match = html.match(/function syncStep4[\s\S]*?\n\}/);
assert.ok(match, "index.html 中未找到 syncStep4 函数体（改名了？）");

function makeSyncStep4(manual, auto) {
  const calls = [];
  const done = (n) => calls.push(["done", n]);
  const undone = (n) => calls.push(["undone", n]);
  const fn = new Function(
    "markStepDone", "markStepUndone", "selectedReferenceIds", "autoReferenceIds",
    "return (" + match[0] + ")"
  )(done, undone, manual, auto);
  return { fn, calls };
}

test("手动 + 自动都为空 → markStepUndone(4)", () => {
  const { fn, calls } = makeSyncStep4([], []);
  fn();
  assert.deepEqual(calls, [["undone", 4]]);
});

test("仅手动勾选 → markStepDone(4)", () => {
  const { fn, calls } = makeSyncStep4(["ref-1"], []);
  fn();
  assert.deepEqual(calls, [["done", 4]]);
});

test("仅自动关联 → markStepDone(4)", () => {
  const { fn, calls } = makeSyncStep4([], ["ref-auto"]);
  fn();
  assert.deepEqual(calls, [["done", 4]]);
});

test("手动 + 自动并存 → 只 markStepDone(4) 一次", () => {
  const { fn, calls } = makeSyncStep4(["ref-1"], ["ref-auto"]);
  fn();
  assert.deepEqual(calls, [["done", 4]]);
});

test("静态断言：简介生成成功回调必须调用 markStepDone(2)", () => {
  assert.match(html, /markStepDone\(2\);\s*\/\/ 简介生成成功即视为完成/,
    "btn-topic-summary 成功分支的 markStepDone(2) 被删了？");
});

test("静态断言：勾选变更与自动关联两处都调用 syncStep4()", () => {
  const occurrences = html.split("syncStep4();").length - 1;
  assert.ok(occurrences >= 2, "syncStep4() 调用点少于 2 处（勾选变更 / 推荐自动关联）");
});
