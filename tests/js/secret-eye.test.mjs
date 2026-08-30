// secretEyeState 纯函数单测（工单 ux-polish/01）：设置页 API key / 视觉 key
// 显隐切换状态机——密码态 → 点击后变明文（按钮文案「隐藏」），反之亦然。
// 运行：node --test "tests/js/*.test.mjs"
import test from "node:test";
import assert from "node:assert/strict";
import { secretEyeState } from "../../src/contest_generator/static/js/fx/settings.js";

test("secretEyeState：密码态 → 明文 + 按钮文案「隐藏」", () => {
  const s = secretEyeState("password");
  assert.equal(s.nextType, "text");
  assert.equal(s.label, "隐藏");
});

test("secretEyeState：明文态 → 密码 + 按钮文案「显示」", () => {
  const s = secretEyeState("text");
  assert.equal(s.nextType, "password");
  assert.equal(s.label, "显示");
});
