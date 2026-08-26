// 步骤 2 / 4 完成判定单测（本轮修复：两步骤此前从未有过 markStepDone 调用）。
// syncStep4 为纯判定（注入 stub markStepDone / markStepUndone 与两个 id 数组）；
// 另加静态断言防回归：简介成功回调必须含 markStepDone(2)。
// fx/draft.js 版本：状态数组与回调显式传参（迁入前闭包捕获主体模块级状态）。
// 静态断言按归属指向 ui/generate-recommend.js（阶段 2 工单 12 重指向：两处
// syncStep4 调用点与 markStepDone(2) 均在该簇；cut 方案复核后非 generate-steps）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";
import { syncStep4 } from "../../src/contest_generator/static/js/fx/draft.js";

const src = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/generate-recommend.js", import.meta.url),
  "utf8"
);

function runSyncStep4(manual, auto) {
  const calls = [];
  const done = (n) => calls.push(["done", n]);
  const undone = (n) => calls.push(["undone", n]);
  syncStep4(manual, auto, done, undone);
  return calls;
}

test("手动 + 自动都为空 → markStepUndone(4)", () => {
  assert.deepEqual(runSyncStep4([], []), [["undone", 4]]);
});

test("仅手动勾选 → markStepDone(4)", () => {
  assert.deepEqual(runSyncStep4(["ref-1"], []), [["done", 4]]);
});

test("仅自动关联 → markStepDone(4)", () => {
  assert.deepEqual(runSyncStep4([], ["ref-auto"]), [["done", 4]]);
});

test("手动 + 自动并存 → 只 markStepDone(4) 一次", () => {
  assert.deepEqual(runSyncStep4(["ref-1"], ["ref-auto"]), [["done", 4]]);
});

test("静态断言：简介生成成功回调必须调用 markStepDone(2)", () => {
  assert.match(src, /markStepDone\(2\);\s*\/\/ 简介生成成功即视为完成/,
    "btn-topic-summary 成功分支的 markStepDone(2) 被删了？");
});

test("静态断言：勾选变更与自动关联两处都调用 syncStep4（参数化）", () => {
  const occurrences = src.split("syncStep4(").length - 1;
  assert.ok(occurrences >= 2, "syncStep4 调用点少于 2 处（勾选变更 / 推荐自动关联）");
});
