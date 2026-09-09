# 01 — 行操作与反缩进

**要做什么：** 让代码编辑器具备 VSCode 同款行级快捷键：Shift+Tab 反缩进（与 Tab 缩进对称，作用于选区/当前行）、Ctrl+Shift+K 删除行、Alt+↑/↓ 移动行、Shift+Alt+↑/↓ 复制行、Ctrl+L 选整行（含行尾）。所有快捷键在光标/选区基础上工作，Enter/Tab/括号等既有行为不回归，并同步进快捷键帮助弹窗（数据单源）。

**被谁阻塞：** 无——可立即开始。

**Type:** task
## Answer

已实现并验证（2025-xx 提交）：

- 新 fx 纯件 `src/contest_generator/static/js/fx/code-lineops.js`：`shiftTab` /
  `deleteLine` / `moveLine` / `copyLine` / `lineRangeOf`（无 DOM，基于
  {value, selStart, selEnd}，返回 {value, start, end}，与 indentLines 同约定）。
- 单测 `tests/js/code-lineops.test.mjs` 25 例全绿（多行/单行/边界/块移动/复制/
  选整行扩展）。
- keydown 管线注册：Shift+Tab / Ctrl+Shift+K / Alt+↑↓ / Shift+Alt+↑↓ / Ctrl+L，
  带 IME 守卫、只读早退；帮助弹窗数据单源同步（fx/code-shortcuts.js）。
- CDP 冒烟 `.scratch/code-page-vscode-overhaul/smoke-01.mjs` 8/8 PASS（含帮助
  弹窗渲染、只读不响应），深色截图 shot-01-lineops-dark.png 存档。
- 全量 `node --test "tests/js/**/*.test.mjs"` 1171 例通过。
- code-review 双轴：Standards 无硬违规（修复 1 处过时 doc 注释）；Spec 无缺失
  无蔓延；撤销栈按计划归工单 04。

**Status:** resolved

## 实现要点

- 新 fx 纯件模块（无 DOM 依赖，可 `node --test` 单测）：`shiftTab`、`deleteLine`、`moveLine`、`copyLine`、`lineRangeOf`（选整行，含行尾处理）；操作基于 {text, selectionStart, selectionEnd} 输入，返回新的 text 与选区（多行选区语义对齐 VSCode）。
- keydown 管线（`ui/codeeditor.js`）新增分支：Shift+Tab / Ctrl+Shift+K / Alt+↑↓ / Shift+Alt+↑↓ / Ctrl+L；受 IME composing 保护；.md 预览态只读文件不响应。
- 快捷键帮助弹窗（`fx/code-shortcuts.js` 数据单源）补充以上条目。
- 程序化编辑写入文本与选区，先沿用现有落地方式（撤销栈问题归 04 处理，此处不扩范围）。

## 验收 checklist

- [ ] `node --test tests/js/` 全部绿（新增 line-ops 纯件测试 + 既有测试无回归）。
- [ ] 深色主题下：多行选中 Shift+Tab 同时反缩进、无选区时缩进当前行。
- [ ] Ctrl+Shift+K 删除当前行/选中行组，光标位置合理。
- [ ] Alt+↑↓ 移动行（单行/多行），光标随行移动；Shift+Alt+↑↓ 复制行。
- [ ] Ctrl+L 选整行（再按扩展选中多行）。
- [ ] 快捷键帮助弹窗出现以上条目，可正常唤起。
- [ ] 既有 Tab/Enter/括号/查找/折叠/保存回归面正常（CDP 冒烟）。

## 真机项集中挂账（2026-09-09 在途盘点）

- 本单仍未勾的验收项属**真机工具链 / 浏览器 CDP / 真实 LLM 额度 / 人工取源 / 历史流程**类，
  已集中到 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md`（那里不写代码，
  验完一项回勾本单对应项即可）；后续盘点不再逐张重判这些项。
