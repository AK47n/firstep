// fmtSeconds 纯函数单测（阶段 2 工单 16：修复中心簇迁 ui/generate-fix.js，
// 纯计算无 DOM → 迁 fx/generate.js；本文档钉格式契约：1 位小数、非有限/负值兜底
// "0.0"）。运行：node --test "tests/js/*.test.mjs"
import test from "node:test";
import assert from "node:assert/strict";
import { fmtSeconds } from "../../src/contest_generator/static/js/fx/generate.js";

test("fmtSeconds：有限非负 → 1 位小数（截断式 toFixed）", () => {
  assert.equal(fmtSeconds(12.34), "12.3");
  assert.equal(fmtSeconds(0), "0.0");
  assert.equal(fmtSeconds(180.0), "180.0");
  assert.equal(fmtSeconds("1.25"), "1.3");   // 数字字符串同契约
});

test("fmtSeconds：非有限 / 负值 / 非数字 → 兜底 0.0", () => {
  assert.equal(fmtSeconds(-1), "0.0");
  assert.equal(fmtSeconds(NaN), "0.0");
  assert.equal(fmtSeconds(Infinity), "0.0");
  assert.equal(fmtSeconds(undefined), "0.0");
  assert.equal(fmtSeconds("abc"), "0.0");
});
