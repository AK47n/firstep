// tests/js/code-editor-window-guard.test.mjs — 代码编辑器窗口/折叠渲染守卫
// （2026-09-09 在途盘点第六轮补口）。
//
// 两个缺陷在 CDP 冒烟里现形（smoke-01 5 项假红 / smoke-07 1 项红），均为 DOM
// 胶水层、纯件单测覆盖不到，本守卫做静态源断言把它们钉住：
//
//   ① 块选区坍缩：窗口化（08/09）后 applyEdit 的「非折叠窗口化」分支只把 end
//      传给 syncTail（窗口按光标重装），多行 Shift+Tab / Alt+↑↓ / Shift+Alt+↑↓
//      的纯件契约 {start, end} 被坍缩成光标 → 修复 = 该分支补
//      `if (start !== end) taSetRange(start, end)`。
//   ② 幽灵占位行：占位行被整体替换 → 折叠全展开、可见行数恰好不变时，syncTail
//      走增量 patch 分支（只 patch lines/hl、不动 gutter），旧折叠 gutter
//      （占位行 + 跳号行号）留在 DOM → 修复 = 该分支加 `!winCache.foldedView`
//      前提（上一版 gutter 不是折叠视图才允许增量）。
//
// 另钉 CDP 冒烟里的块选区期望不被悄悄放宽（验收证据不许静默变弱）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const ui = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/codeeditor.js", import.meta.url), "utf8");
const smoke01 = readFileSync(
  new URL("../../.scratch/code-page-vscode-overhaul/smoke-01.mjs", import.meta.url), "utf8");

test("applyEdit 非折叠窗口化分支：块选区还原（start !== end → taSetRange）", () => {
  const fnAt = ui.indexOf("function applyEdit(");
  assert.ok(fnAt > 0, "找不到 applyEdit");
  const winAt = ui.indexOf("if (taWinInfo && !viewModel) {", fnAt);
  const foldAt = ui.indexOf("if (viewModel) {", fnAt);
  assert.ok(winAt > 0 && foldAt > winAt, "applyEdit 分支结构变化（窗口化 / 折叠分支顺序）");
  const branch = ui.slice(winAt, foldAt);
  assert.ok(branch.includes("syncTail(Math.max(0, end | 0));"),
    "窗口化分支的 syncTail 调用变了——块选区还原的前提要重新确认");
  assert.ok(branch.includes("if (start !== end) taSetRange(start, end);"),
    "块选区还原缺失：多行行操作（Shift+Tab / Alt+↑↓ / Shift+Alt+↑↓）会坍缩成光标");
});

test("syncTail 增量 patch：上一版 gutter 为折叠视图时不走（防幽灵占位行）", () => {
  const at = ui.indexOf("const viewText = viewModel ? viewModel.text : tab.content;");
  assert.ok(at > 0, "找不到 syncTail 的 viewText 计算");
  const tail = ui.slice(at, at + 1200);
  assert.ok(tail.includes("!winCache.foldedView"),
    "增量 patch 分支缺 foldedView 前提：折叠全展开且行数不变时 gutter 不重建（幽灵占位行 + 行号错位）");
  assert.ok(ui.includes("foldedView: !!viewModel,"),
    "winBuild 未记录 foldedView（gutter 来源标记）——增量 patch 判据失去依据");
});

test("CDP 冒烟 smoke-01：块选区期望仍在（防悄悄放宽）", () => {
  for (const needle of [
    'value: "a\\n  b\\nc", sel: [0, 5]',   // Shift+Tab 多行反缩进：选区覆盖整段
    'value: "a\\nb\\nb", sel: [4, 4]',     // Shift+Alt+↓ 复制行：光标落副本
  ]) {
    assert.ok(smoke01.includes(needle), `smoke-01 缺块选区断言：${needle}`);
  }
});
