// fx/write-guard.js 纯函数单测（工单 code-write-guard/01）：判定 / 标题 / 文案。
// 直接 import，子串断言防脆。运行：node --test tests/js/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  writeGuardNeeded,
  writeGuardTitle,
  writeGuardMessage,
  WRITE_GUARD_ACTIONS,
} from "../../src/contest_generator/static/js/fx/write-guard.js";

test("writeGuardNeeded：仅生成上下文 + 脏标签数 > 0 才提示", () => {
  assert.equal(writeGuardNeeded(true, 1), true);
  assert.equal(writeGuardNeeded(true, 3), true);
  assert.equal(writeGuardNeeded(false, 1), false);   // 非上下文
  assert.equal(writeGuardNeeded(true, 0), false);    // 无脏
  assert.equal(writeGuardNeeded(true, null), false);
  assert.equal(writeGuardNeeded(undefined, 2), false);
});

test("writeGuardTitle：固定中文标题", () => {
  assert.equal(writeGuardTitle(), "代码栏有未保存修改");
});

test("writeGuardMessage：动作名 + N 个文件 + 引导；空动作名兜底；转义", () => {
  const msg = writeGuardMessage("一键编译修复", 2);
  assert.ok(msg.includes("『一键编译修复』"));
  assert.ok(msg.includes("2 个文件未保存"));
  assert.ok(msg.includes("保存全部"));
  const fallback = writeGuardMessage("", 1);
  assert.ok(fallback.includes("『该操作』"));
  assert.ok(fallback.includes("1 个文件未保存"));
  const escMsg = writeGuardMessage("<b>动作</b>", 1);
  assert.ok(escMsg.includes("&lt;b&gt;"));
  assert.ok(!escMsg.includes("<b>"));
});

test("WRITE_GUARD_ACTIONS：写盘动作名单源冻结（评审整改——防散落裸串改名漏改）", () => {
  assert.deepEqual(Object.keys(WRITE_GUARD_ACTIONS).sort(), [
    "continueFix", "deepen", "fix", "params", "revise", "task", "taskFeedback",
  ]);
  assert.equal(WRITE_GUARD_ACTIONS.fix, "一键编译修复");
  assert.equal(WRITE_GUARD_ACTIONS.continueFix, "继续修复");
  assert.equal(WRITE_GUARD_ACTIONS.revise, "执行修订");
  assert.equal(WRITE_GUARD_ACTIONS.deepen, "深化");
  assert.equal(WRITE_GUARD_ACTIONS.task, "做这一步");
  assert.equal(WRITE_GUARD_ACTIONS.taskFeedback, "按反馈修复");
  assert.equal(WRITE_GUARD_ACTIONS.params, "改值并编译");
  assert.ok(Object.isFrozen(WRITE_GUARD_ACTIONS));
});
