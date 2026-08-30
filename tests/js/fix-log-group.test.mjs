// fixLogGroupHidden 纯函数单测（工单 ux-polish/01）：修复中心「编译输出」分组
// 显隐决策——无输出（空 / 空白 / null / undefined）→ 隐藏，有输出 → 显示。
// 运行：node --test "tests/js/*.test.mjs"
import test from "node:test";
import assert from "node:assert/strict";
import { fixLogGroupHidden } from "../../src/contest_generator/static/js/fx/generate.js";

test("fixLogGroupHidden：空 / 空白 / 非字符串 → 隐藏", () => {
  assert.equal(fixLogGroupHidden(""), true);
  assert.equal(fixLogGroupHidden("   \n\t "), true);
  assert.equal(fixLogGroupHidden(undefined), true);
  assert.equal(fixLogGroupHidden(null), true);
});

test("fixLogGroupHidden：有内容（含 warnings 输出）→ 显示", () => {
  assert.equal(fixLogGroupHidden("main.c(12): error #20: ..."), false);
  assert.equal(fixLogGroupHidden("warning: unused variable"), false);
  assert.equal(fixLogGroupHidden("0"), false);
});
