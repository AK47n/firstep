// fx/ai-actions.js 纯函数单测（工单 code-editor-refine/07）：选中代码快捷
// 动作（解释 / 加中文注释 / 重构 / 问 AI）——动作清单 + 模板 + prompt 拼装。
// 直接 import，子串断言防脆。运行：node --test tests/js/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  AI_SELECTION_ACTIONS,
  AI_ACTION_TEMPLATES,
  AI_ASK_ACTION_ID,
  buildActionPrompt,
} from "../../src/contest_generator/static/js/fx/ai-actions.js";
import { selectionContextText } from "../../src/contest_generator/static/js/fx/ai-diff.js";

test("AI_SELECTION_ACTIONS：四项 解释/加中文注释/重构/问 AI（顺序稳定 + ask id 单源）", () => {
  assert.deepEqual(AI_SELECTION_ACTIONS.map((a) => a.label),
    ["解释", "加中文注释", "重构", "问 AI"]);
  assert.deepEqual(AI_SELECTION_ACTIONS.map((a) => a.id),
    ["explain", "comment", "refactor", AI_ASK_ACTION_ID]);
  assert.equal(AI_ASK_ACTION_ID, "ask");
});

test("buildActionPrompt：解释 = 模板（只解释不修改）+ 选区引用", () => {
  const p = buildActionPrompt("explain", {
    path: "main.c", lang: "c", startLine: 3, endLine: 5, code: "int x = 1;",
  });
  assert.ok(p.includes("解释"));
  assert.ok(p.includes("不要修改代码"));
  assert.ok(p.includes("【代码引用 · main.c · 第 3-5 行】"));
  assert.ok(p.includes("```c\nint x = 1;\n```"));
  assert.ok(!p.includes("只输出修改后"));
});

test("buildActionPrompt：加中文注释 / 重构 = 模板 + DIFF 约束 + 选区引用", () => {
  const ctx = { path: "src/app.c", lang: "c", startLine: 1, endLine: 2, code: "void f() {}" };
  const c = buildActionPrompt("comment", ctx);
  assert.ok(c.includes("中文注释"));
  assert.ok(c.includes("只输出修改后的完整代码片段"));
  assert.ok(c.includes("<DIFF>"));
  assert.ok(c.includes("src/app.c"));
  const r = buildActionPrompt("refactor", ctx);
  assert.ok(r.includes("重构"));
  assert.ok(r.includes("保持行为不变"));
  assert.ok(r.includes("<DIFF>"));
});

test("buildActionPrompt：问 AI / 未知动作 = 纯选区引用（原行为）", () => {
  const ctx = { path: "main.c", lang: "", startLine: 1, endLine: 1, code: "int x;" };
  const ref = selectionContextText("main.c", "", 1, 1, "int x;");
  assert.equal(buildActionPrompt("ask", ctx), ref);
  assert.equal(buildActionPrompt("nope", ctx), ref);
});

test("buildActionPrompt：空选区防护（ctx 缺省/空 code 不抛，无字面 undefined）", () => {
  const p = buildActionPrompt("explain", { path: "a.c", startLine: 1, endLine: 1, code: "" });
  assert.ok(typeof p === "string" && p.includes("【代码引用 · a.c · 第 1-1 行】"));
  const none = buildActionPrompt("explain", null);
  assert.ok(typeof none === "string" && none.includes("【代码引用 ·"));
  assert.ok(!none.includes("undefined"));
  assert.ok(!none.includes("NaN"));
});

test("AI_ACTION_TEMPLATES：三个动作模板均非空", () => {
  assert.equal(Object.keys(AI_ACTION_TEMPLATES).length, 3);
  for (const id of ["explain", "comment", "refactor"]) {
    assert.ok(AI_ACTION_TEMPLATES[id].length > 10, id);
  }
});
