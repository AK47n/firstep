// exit-guard.test.mjs — fx/exit-guard.js 未保存退出保护纯件单测
// （工单 code-editor-refine/01：切目录三选消息 + 模态 HTML）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  unsavedSwitchMessage,
  unsavedSwitchModalHTML,
} from "../../src/contest_generator/static/js/fx/exit-guard.js";

const tab = (path) => ({ path, content: "x", savedContent: "y" });

test("unsavedSwitchMessage: 计数与路径清单（含目标目录）", () => {
  const msg = unsavedSwitchMessage("C:\\proj\\a", [tab("main.c"), tab("util.c")]);
  assert.ok(msg.includes("C:\\proj\\a"), "消息含目标目录");
  assert.ok(msg.includes("2 个文件未保存"), "计数正确");
  assert.ok(msg.includes("「main.c」"), "列首个路径");
  assert.ok(msg.includes("「util.c」"), "列第二个路径");
  assert.ok(msg.includes("保存全部并切换"), "提示保存动作");
  assert.ok(msg.includes("放弃修改并切换"), "提示放弃动作");
});

test("unsavedSwitchMessage: 路径 HTML 转义", () => {
  const msg = unsavedSwitchMessage("d", [tab('<script>alert(1)</script>.c')]);
  assert.ok(!msg.includes("<script>"), "原始 script 不出现");
  assert.ok(msg.includes("&lt;script&gt;"), "转义后出现");
});

test("unsavedSwitchMessage: 超长清单截断（显示 8 个 + 等 N 个）", () => {
  const tabs = Array.from({ length: 11 }, (_, i) => tab("f" + i + ".c"));
  const msg = unsavedSwitchMessage("d", tabs);
  assert.ok(msg.includes("11 个文件未保存"), "计数为全量");
  assert.ok(msg.includes("「f0.c」"), "第一个显示");
  assert.ok(msg.includes("「f7.c」"), "第八个显示");
  assert.ok(!msg.includes("「f8.c」"), "第九个不显示");
  assert.ok(msg.includes("等 3 个"), "省略数正确");
});

test("unsavedSwitchMessage: 零脏标签（边界）", () => {
  const msg = unsavedSwitchMessage("d", []);
  assert.ok(msg.includes("0 个文件未保存"), "零计数");
  assert.ok(!msg.includes("未保存："), "无路径清单（无冒号列表）");
});

test("unsavedSwitchModalHTML: 三动作按钮 + 标题 + 消息转义", () => {
  const html = unsavedSwitchModalHTML({ dir: '<d>', dirtyTabs: [tab("a.c")] });
  assert.ok(html.includes('data-unsaved-action="save"'), "保存按钮");
  assert.ok(html.includes('data-unsaved-action="discard"'), "放弃按钮");
  assert.ok(html.includes('data-unsaved-action="cancel"'), "取消按钮");
  assert.ok(html.includes("有未保存的修改"), "标题");
  assert.ok(!html.includes("<d>"), "目录名转义");
  assert.ok(html.includes("code-unsaved-modal"), "模态类名");
});
