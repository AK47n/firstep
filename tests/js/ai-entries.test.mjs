// tests/js/ai-entries.test.mjs — 「和 AI 聊」入口收敛守卫（工单 ux-walkthrough-02/23）：
// ①各入口可见定位说明（全局商量 / 问 AI 参数 / 买件商量边界）+ ②长跑直达按钮
// （母版提炼 / 修复中心 / 修订执行 × data-goto-global-chat）+ ③generate-tasks 直达监听 +
// ④推荐结果区与任务推进区边界说明 + ⑤第 12 步交接提示词呼应文案。静态守卫式。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8",
);
const tasksUi = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/generate-tasks.js", import.meta.url),
  "utf8",
);
const recommendFx = readFileSync(
  new URL("../../src/contest_generator/static/js/fx/recommend.js", import.meta.url),
  "utf8",
);

test("入口定位说明：全局商量 / 问 AI 参数 各有一句可见边界", () => {
  assert.match(html, /针对整个工程：架构取舍 \/ 赛道策略/, "全局商量定位说明");
  assert.match(html, /买件选型请用推荐结果区的「和 AI 商量」/, "全局商量→买件边界");
  assert.match(html, /针对 main\.c 里的具体数值/, "问 AI 参数定位说明");
  assert.match(html, /架构级疑问用上面的「全局商量」/, "参数→全局边界");
});

test("推荐结果区与任务推进区边界说明", () => {
  assert.match(recommendFx, /本区只谈选型与买件/, "买件商量边界说明");
  assert.match(recommendFx, /代码 \/ 赛题逻辑疑问请用第 11 步任务推进的「全局商量（工程级）」/,
    "买件→任务推进边界");
});

test("长跑屏幕直达入口：母版提炼 / 修复中心 / 修订执行 各一个 data-goto-global-chat", () => {
  const count = (html.match(/data-goto-global-chat/g) || []).length;
  assert.equal(count, 3, "应有 3 个直达按钮（实际 " + count + "）");
  // 三个位置锚点
  assert.match(html, /id="btn-distill"[\s\S]*?data-goto-global-chat/, "母版提炼按钮行");
  assert.match(html, /id="fix-center-toolchain"[\s\S]*?data-goto-global-chat/, "修复中心状态行");
  assert.match(html, /id="revise-exec-status"[\s\S]*?data-goto-global-chat/, "修订执行状态行");
});

test("generate-tasks 直达监听：切顶层生成页 + 子页签 + 展开全局商量 + 未加载目录提示", () => {
  assert.match(tasksUi, /data-goto-global-chat/, "监听挂在 document 委托");
  assert.match(tasksUi, /nav button\[data-tab="generate"\]/, "先切顶层生成页（母版页直达，评审 H1 整改）");
  assert.match(tasksUi, /revise-tab\[data-tab="tasks"\]/, "切任务推进页签（经按钮 click 无 import 环）");
  assert.match(tasksUi, /void tasksChatToggle\(\)/, "展开全局商量");
  assert.match(tasksUi, /请先在「修订」页签加载输出目录/, "未加载目录引导");
  assert.match(tasksUi, /tasks\.outputDir \|\| reviseGetDir\(\)/, "守卫与聊天同口径（评审整改）");
});

test("每卡「问这里」常显一句定位说明（与其余入口可见说明呼应）", () => {
  const taskFx = readFileSync(
    new URL("../../src/contest_generator/static/js/fx/task.js", import.meta.url),
    "utf8",
  );
  assert.match(taskFx, /task-dialog-scope/, "按钮旁常显定位 span");
  assert.match(taskFx, /本卡只聊这一步；工程级疑问用「全局商量（工程级）」/, "定位说明可见一句");
});

test("第 12 步交接提示词与收敛后入口呼应（同名：全局商量（工程级））", () => {
  assert.match(html, /工具内已能「全局商量（工程级）」（第 11 步任务推进）/,
    "交接卡提示呼应入口收敛与同名术语");
});
