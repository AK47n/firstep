// tests/js/handoff-note-guard.test.mjs — Y4 交接提示词说明结构护栏
// （工单 newcomer-glossary/03）：静态断言第 12 步卡说明文案存在且位于
// #btn-handoff 上方、「去任务推进」按钮存在、ui/handoff.js 导出
// goTaskProgress/initHandoffNote 并复用 switchReviseTab、index.html 成对接入。
// 防删防改名（对齐 ai-action-refs / glossary-refs 先例）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
const handoff = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/handoff.js", import.meta.url),
  "utf8"
);
const reviseTabs = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/revise-tabs.js", import.meta.url),
  "utf8"
);

test("第 12 步卡含 handoff-note 说明（含「一般」与「外部 AI」）", () => {
  const m = html.match(/<p class="handoff-note">([^<]+)<\/p>/);
  assert.ok(m, "缺 handoff-note");
  assert.ok(m[1].includes("一般"), "文案缺「一般」");
  assert.ok(m[1].includes("外部 AI"), "文案缺「外部 AI」");
});

test("「去任务推进」按钮存在且在 handoff-note 与 #btn-handoff 之间", () => {
  const noteAt = html.indexOf('class="handoff-note"');
  const goAt = html.indexOf('id="btn-goto-tasks"');
  const handoffAt = html.indexOf('id="btn-handoff"');
  assert.ok(noteAt >= 0 && goAt > noteAt && handoffAt > goAt,
    "顺序应为 handoff-note → btn-goto-tasks → btn-handoff");
});

test("ui/handoff.js 导出 goTaskProgress 与 initHandoffNote", () => {
  assert.match(handoff, /export function goTaskProgress\(\)/);
  assert.match(handoff, /export function initHandoffNote\(\)/);
});

test("ui/revise-tabs.js 仍导出 switchReviseTab（既有事实，防改名）", () => {
  assert.match(reviseTabs, /export function switchReviseTab\(key, opts\)/);
});

test("goTaskProgress 复用 switchReviseTab（不新写页签逻辑）", () => {
  assert.match(handoff, /import \{ \$ \} from "\/js\/app\.js"/);
  assert.match(handoff, /import \{ switchReviseTab \} from "\/js\/ui\/revise-tabs\.js"/);
  assert.match(handoff, /switchReviseTab\("tasks", \{ user: true \}\)/);
  assert.match(handoff, /card-revise/);
});

test("index.html 成对接入：import + initHandoffNote() 调用", () => {
  assert.match(html, /import \{ initHandoffNote \} from "\/js\/ui\/handoff\.js"/);
  assert.match(html, /initHandoffNote\(\);/);
});
