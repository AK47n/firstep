// revise-tabs.test.mjs — fx/revise-tabs.js 第11步页签纯函数单测
// （工单 step11-tabs-ui/01）：页签定义 / 条标记（激活态 / aria / 徽章槽位）/
// 徽章文案规则 / 方向键循环 / 面板映射。直接 import fx 模块（不再字符串提取）。
// 工单 beginner-gap-closure/01 扩展：ui/generate-tasks.js 空态指路文案、
// ui/revise-tabs.js 默认激活与自动切换条件（glue 层无法 import，按守卫先例静态钉住）。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  REVISE_TABS, reviseTabsHTML, revisePanelFor, reviseTabNext, reviseTabBadge,
} from "../../src/contest_generator/static/js/fx/revise-tabs.js";

test("REVISE_TABS：4 页签定义（key + label）——主路径「任务推进」居首", () => {
  assert.deepEqual(REVISE_TABS.map((t) => t.key), ["tasks", "revise", "params", "delivery"]);
  assert.deepEqual(REVISE_TABS.map((t) => t.label), ["任务推进", "修订", "参数速调", "交付"]);
});

test("revisePanelFor：key → 面板 id 契约", () => {
  assert.equal(revisePanelFor("revise"), "revise-panel-revise");
  assert.equal(revisePanelFor("tasks"), "revise-panel-tasks");
  assert.equal(revisePanelFor("params"), "revise-panel-params");
  assert.equal(revisePanelFor("delivery"), "revise-panel-delivery");
});

test("reviseTabsHTML：4 按钮 + data-tab + aria-controls + aria-selected + roving tabindex", () => {
  const html = reviseTabsHTML(REVISE_TABS, "tasks", {});
  assert.equal(html.match(/class="revise-tab(?: active)?"/g).length, 4);
  for (const t of REVISE_TABS) {
    assert.ok(html.includes('id="revise-tab-' + t.key + '"'));
    assert.ok(html.includes('data-tab="' + t.key + '"'));
    assert.ok(html.includes('aria-controls="revise-panel-' + t.key + '"'));
  }
  // 激活页签
  const tasksBtn = '" data-tab="tasks" aria-controls="revise-panel-tasks" aria-selected="true" tabindex="0"';
  assert.ok(html.includes(tasksBtn), "tasks 应为激活页签（aria-selected=true / tabindex=0）");
  assert.ok(html.includes('" data-tab="revise" aria-controls="revise-panel-revise" aria-selected="false" tabindex="-1"'));
});

test("reviseTabsHTML：徽章槽位恒渲染，空徽章带 hidden，label 转义", () => {
  const html = reviseTabsHTML(
    [{ key: "a", label: '标题"引号"' }, { key: "b", label: "B" }],
    "a",
    { a: "3/7" }
  );
  assert.ok(html.includes('<span class="revise-tab-badge">3/7</span>'));
  assert.ok(html.includes('<span class="revise-tab-badge hidden"></span>'));
  assert.ok(html.includes('标题&quot;引号&quot;'));
});

test("reviseTabBadge：修订 ✓ / 空", () => {
  assert.equal(reviseTabBadge("revise", { loaded: true }), "✓");
  assert.equal(reviseTabBadge("revise", { loaded: false }), "");
  assert.equal(reviseTabBadge("revise", {}), "");
});

test("reviseTabBadge：任务 N/M（total=0 不显示）", () => {
  assert.equal(reviseTabBadge("tasks", { done: 3, total: 7 }), "3/7");
  assert.equal(reviseTabBadge("tasks", { done: 0, total: 0 }), "");
  assert.equal(reviseTabBadge("tasks", {}), "");
});

test("reviseTabBadge：参数 N（count=0 不显示）", () => {
  assert.equal(reviseTabBadge("params", { count: 5 }), "5");
  assert.equal(reviseTabBadge("params", { count: 0 }), "");
  assert.equal(reviseTabBadge("params", {}), "");
});

test("reviseTabBadge：交付 ✓/⚠（未检查不显示）", () => {
  assert.equal(reviseTabBadge("delivery", { checked: true, ok: true }), "✓");
  assert.equal(reviseTabBadge("delivery", { checked: true, ok: false }), "⚠");
  assert.equal(reviseTabBadge("delivery", { checked: false }), "");
  assert.equal(reviseTabBadge("delivery", {}), "");
});

test("reviseTabNext：左右循环 + 回绕", () => {
  assert.equal(reviseTabNext(0, 1, 4), 1);
  assert.equal(reviseTabNext(1, 1, 4), 2);
  assert.equal(reviseTabNext(3, 1, 4), 0);   // 末位右移回绕
  assert.equal(reviseTabNext(0, -1, 4), 3);  // 首位左移回绕
  assert.equal(reviseTabNext(2, -1, 4), 1);
  assert.equal(reviseTabNext(0, 1, 0), -1);  // 空列表
});

test("reviseTabNext：非数字 index 兜底为 0", () => {
  assert.equal(reviseTabNext(NaN, 1, 4), 1);
  assert.equal(reviseTabNext(undefined, -1, 4), 3);
});

test("任务推进空态仍指路「修订」页签（ui 文案守卫）", () => {
  const tasks = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/generate-tasks.js", import.meta.url),
    "utf8"
  );
  assert.ok(tasks.includes("请先在「修订」页签加载当前会话或历史目录"),
    "任务推进空态应指路到「修订」页签加载上下文");
});

test("ui/revise-tabs.js：默认激活「任务推进」+ 自动切换带显式条件（glue 源守卫）", () => {
  const uiSrc = readFileSync(
    new URL("../../src/contest_generator/static/js/ui/revise-tabs.js", import.meta.url),
    "utf8"
  );
  assert.match(uiSrc, /const state = \{ active: "tasks"/);
  assert.match(uiSrc, /if \(!state\.userPicked && state\.active !== "tasks"\)/);
});
