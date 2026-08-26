// truncate 纯函数单测（前端 ES 模块化阶段 2 工单 05）：已迁 static/js/fx/core.js。
// 契约：text 转字符串；长度 ≤ n 原样；否则 slice(0, n) + "…"。
// 运行：node --test "tests/js/*.test.mjs"
import test from "node:test";
import assert from "node:assert/strict";
import { truncate } from "../../src/contest_generator/static/js/fx/core.js";

test("truncate：长度内原样 / 超长截断 + 省略号", () => {
  assert.equal(truncate("abc", 5), "abc");
  assert.equal(truncate("abcdef", 5), "abcde…");
  assert.equal(truncate("abcdef", 6), "abcdef");
});

test("truncate：n=0 只留省略号 / 非字符串入参转字符串", () => {
  assert.equal(truncate("ab", 0), "…");
  assert.equal(truncate(12345, 3), "123…");
});
