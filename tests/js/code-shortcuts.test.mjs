// fx/code-shortcuts.js 纯函数单测（工单 code-editor-shortcut-help/01）：快捷键
// 帮助数据分组完整性 + 帮助浮层 HTML（键帽/分组/转义）。直接 import，子串
// 断言防脆。运行：node --test tests/js/
import test from "node:test";
import assert from "node:assert/strict";
import { SHORTCUT_GROUPS, shortcutHelpHTML } from "../../src/contest_generator/static/js/fx/code-shortcuts.js";

test("SHORTCUT_GROUPS：三组（编辑/查找/视图）且每项键位数组与说明非空", () => {
  assert.deepEqual(SHORTCUT_GROUPS.map((g) => g.title), ["编辑", "查找", "视图"]);
  for (const g of SHORTCUT_GROUPS) {
    assert.ok(g.items.length > 0, g.title + " 组不应为空");
    for (const it of g.items) {
      assert.ok(Array.isArray(it.keys) && it.keys.length > 0, g.title + " 组键位应为非空数组");
      for (const k of it.keys) assert.ok(k && k.trim(), g.title + " 组存在空键帽");
      assert.ok(it.label && it.label.trim(), g.title + " 组存在空说明");
    }
  }
});

test("SHORTCUT_GROUPS：覆盖全部常用快捷键（关键条目）", () => {
  const all = SHORTCUT_GROUPS.flatMap((g) => g.items).flatMap((it) => it.keys).join("|");
  for (const k of ["Ctrl+S", "Ctrl+F", "Ctrl+H", "Esc", "Backspace",
    "Ctrl+Shift+[", "Ctrl+Shift+]", "Ctrl+滚轮", "Tab", "Enter", "Shift+Enter",
    "Ctrl+W", "Ctrl+B"]) {
    assert.ok(all.includes(k), "缺少快捷键条目: " + k);
  }
  // 鼠标手势也在册
  assert.ok(all.includes("中键"));
  assert.ok(all.includes("拖拽"));
});

test("shortcutHelpHTML：键帽/分组/标签渲染（替代键位各一帽 + 或分隔）", () => {
  const html = shortcutHelpHTML();
  assert.match(html, /class="code-shortcuts-group">编辑</);
  assert.match(html, /class="code-shortcuts-group">查找</);
  assert.match(html, /class="code-shortcuts-group">视图</);
  assert.match(html, /<kbd class="code-kbd">Ctrl\+S<\/kbd>/);
  assert.match(html, /<kbd class="code-kbd">Ctrl\+Shift\+\[<\/kbd>/);
  assert.match(html, /保存当前文件/);
  assert.match(html, /折叠光标所在代码块/);
  // 替代键位各一帽 + "/" 分隔符（评审整改：不锁 kbd→or→kbd 拼接顺序，防脆）
  assert.match(html, /<kbd class="code-kbd">Enter<\/kbd>/);
  assert.match(html, /<kbd class="code-kbd">Shift\+Enter<\/kbd>/);
  assert.match(html, /<span class="code-shortcuts-or">\/<\/span>/);
});

test("shortcutHelpHTML：无原始未转义尖括号（数据静态仍约束转义纪律）", () => {
  const html = shortcutHelpHTML();
  assert.ok(!html.includes("<script"), "帮助内容不应含未转义脚本标签");
  // 键帽与标签均经过 esc：<> 原样成为实体（防未来数据里出现）
  assert.ok(!/[<>]/.test(html.replace(/<[a-z/][^>]*>/gi, "")), "文本节点不应含裸尖括号");
});
