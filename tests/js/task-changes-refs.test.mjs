// 结构护栏（工单 task-changes-inline/01+02）：任务执行结果并入任务卡——
// fx 槽位锚点、taskChangesHTML 纯函数、胶水层卡内注入、复插路径、CSS。
// 防删防改名。注：renderIdeaFixResult（直接修正面板，不绑任务卡）仍生成
// id="tasks-result"——护栏按函数分隔，不断言全局无该 id。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const root = "../../src/contest_generator/static/js/";
const read = (p) => readFileSync(new URL(p, import.meta.url), "utf8");

const fxSrc = read(root + "fx/task.js");
const uiSrc = read(root + "ui/generate-tasks.js");
const html = read("../../src/contest_generator/static/index.html");

test("fx/task.js 导出 taskChangesHTML 且 taskCardHTML 含 data-changes-anchor 槽位", () => {
  assert.match(fxSrc, /export function taskChangesHTML\(task, data, opts\)/);
  assert.match(fxSrc, /data-changes-anchor/);
  // 槽位在历史区之后（taskIterationsHTML 与锚点相邻）
  const anchorIdx = fxSrc.indexOf("data-changes-anchor");
  assert.ok(anchorIdx > fxSrc.indexOf("taskIterationsHTML(task)"), "锚点位于历史区之后");
});

test("ui/generate-tasks.js import taskChangesHTML 且执行结果走卡内注入", () => {
  assert.match(uiSrc, /taskChangesHTML/);
  assert.match(uiSrc, /function renderTaskChanges\(taskId, data\)/);
  // 注入 = 卡内锚点 afterend（替代网格末尾 beforeend 结果面板）
  assert.match(uiSrc, /anchors?\.insertAdjacentHTML\("afterend", html\)/);
  assert.doesNotMatch(uiSrc, /function tasksRenderResult\(/);
});

test("tasksExecute 完成链路调用 renderTaskChanges + lastWiringResult 复插路径保留", () => {
  assert.match(uiSrc, /renderTaskChanges\(taskId, data\)/);
  assert.match(uiSrc, /renderTaskChanges\(lastWiringResult\.taskId, lastWiringResult\.data\)/);
  assert.match(uiSrc, /lastWiringResult = \{ taskId, data, dir/);
});

test("直接修正面板 renderIdeaFixResult 保留（不绑任务卡，网格末尾 id=tasks-result）", () => {
  assert.match(uiSrc, /function renderIdeaFixResult\(data\)/);
  assert.match(uiSrc, /id="tasks-result"/);
});

test("index.html 含 .task-changes 样式（details 容器 + 背景 + summary 指针）", () => {
  assert.match(html, /\.task-changes \{ margin-top: var\(--space-2\); border: 1px solid var\(--border\);/);
  assert.match(html, /\.task-changes > summary \{ cursor: pointer;/);
  assert.match(html, /\.task-changes-body \{/);
});
