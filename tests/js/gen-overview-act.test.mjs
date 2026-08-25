// overviewFillPlan / overviewReadyToGenerate 纯函数单测（工单 gen-overview-act/01）：
// 一键补齐计划（关键路径 1/3/6 + 手动模式输出目录缺失）与就绪判定（复用
// generateReadinessChecks，与 btn-generate 前置校验同源）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

// 括号配平提取（同 gen-overview.test.mjs 范式：函数体含 `} else {` 时
// naive 正则会在第一个顶格 `}` 截断）
function extract(name) {
  const start = html.indexOf("function " + name);
  assert.ok(start !== -1, "index.html 中未找到 " + name + " 函数体（改名了？）");
  const open = html.indexOf("{", start);
  assert.ok(open !== -1, name + " 函数体缺少左花括号");
  let depth = 0;
  for (let i = open; i < html.length; i++) {
    if (html[i] === "{") depth++;
    else if (html[i] === "}") {
      depth--;
      if (depth === 0) {
        return new Function("return (" + html.slice(start, i + 1) + ")")();
      }
    }
  }
  throw new Error("未找到 " + name + " 函数体结束花括号");
}

const overviewFillPlan = extract("overviewFillPlan");
const overviewReadyToGenerate = extract("overviewReadyToGenerate");

test("overviewFillPlan 全缺：按 1→3→6 顺序，6 不可采用 = spotlight", () => {
  const plan = overviewFillPlan([], false, false);
  assert.deepEqual(plan, [
    { n: 1, action: "focus" },
    { n: 3, action: "spotlight" },
    { n: 6, action: "spotlight" },
  ]);
});

test("overviewFillPlan 可自动采用（有推荐且清单空）：步骤 6 = adopt", () => {
  const plan = overviewFillPlan([], true, false);
  assert.deepEqual(plan, [
    { n: 1, action: "focus" },
    { n: 3, action: "spotlight" },
    { n: 6, action: "adopt" },
  ]);
});

test("overviewFillPlan 已填题面：跳过 1，保留 3/6", () => {
  const plan = overviewFillPlan([1], true, false);
  assert.deepEqual(plan, [
    { n: 3, action: "spotlight" },
    { n: 6, action: "adopt" },
  ]);
});

test("overviewFillPlan 仅剩输出目录缺失：只列步骤 9 focus-dir", () => {
  const plan = overviewFillPlan([1, 3, 6], false, true);
  assert.deepEqual(plan, [{ n: 9, action: "focus-dir" }]);
});

test("overviewFillPlan 全齐：返回空数组（不显示一键补齐）", () => {
  const plan = overviewFillPlan([1, 3, 6], true, false);
  assert.deepEqual(plan, []);
});

test("overviewReadyToGenerate 全部检查 ok → true", () => {
  const checks = [
    { step: 3, ok: true }, { step: 6, ok: true },
    { step: 1, ok: true }, { step: 9, ok: true },
  ];
  assert.equal(overviewReadyToGenerate(checks), true);
});

test("overviewReadyToGenerate 任一检查不 ok → false", () => {
  const checks = [
    { step: 3, ok: true }, { step: 6, ok: true },
    { step: 1, ok: false }, { step: 9, ok: true },
  ];
  assert.equal(overviewReadyToGenerate(checks), false);
});

test("overviewReadyToGenerate 空检查数组 → true（无阻塞项）", () => {
  assert.equal(overviewReadyToGenerate([]), true);
});
