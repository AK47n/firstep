# 03 — 查找替换增强

**要做什么：** 文件内查找/替换升级为 VSCode 式流程：Ctrl+H 聚焦替换输入框；替换区新增「替换单个命中」「替换并跳下一处」按钮，保留既有「全部替换」；替换后命中计数与当前命中位置联动刷新；替换单个命中后焦点/选区落在下一处命中，便于逐步审查。

**被谁阻塞：** 无——可立即开始。

**Type:** task
## Answer

已实现并验证：

- fx/codeeditor.js 新增 `replaceOneAt(src, needle, replacement, hitIndex)`：
  与 codeFindRanges 同语义（大小写不敏感、非重叠、不跨行、查询 trim）替换
  第 hitIndex 个命中，返回 {value, replaced, total, next, at}——next 为替换点
  之后首个命中（不环绕），at 为替换插入点（供光标落位）。
- ui/codeeditor.js：`replaceOneInActiveFile(replacement, jumpToNext)`（模型层
  替换、折叠安全；jumpToNext 聚焦下一命中）；抽 `rebaseModelContent` 供
  replaceAll/replaceOne 共用；`focusFindRange` 折叠态模型→视图映射。
- 侧栏新增「替换」「替换并下一处」按钮（aria/title）；Ctrl+H 聚焦替换输入
  （既有）保留；计数联动（查找计数 + 「将替换 N 处」）。
- 单测 `tests/js/code-replace-one.test.mjs` 6 例全绿；CDP 冒烟
  `smoke-03.mjs` 9/9 PASS（含全部替换回归）；全量测试 1189 例通过。

**Status:** resolved

## 实现要点

- fx 纯件 `replaceOneAt`：给定 text / 查找词 / 当前命中索引（或选区），替换当前命中并返回下一命中位置（替换后光标/选区落在该处）；纯逻辑可单测。
- 右侧栏（`#code-find-input` / `#code-replace-input`）新增两个按钮（带 aria-label/title）；Ctrl+H 从编辑器聚焦替换输入（若替换输入隐藏则先展开）。
- 计数联动：查找/替换后更新命中计数文案；无命中时替换按钮禁用。
- 替换属于程序化编辑，写入路径沿用现状（撤销栈归 04）。

## 验收 checklist

- [ ] 纯件测试：替换单个命中、替换并跳下一处（含同一词多次出现、跨行）、替换末个命中后回绕/停留在合理位置。
- [ ] 深色主题下：Ctrl+H 聚焦替换输入；「替换」逐个命中、替换后选中下一个；「全部替换」仍可用；计数随操作更新。
- [ ] 无命中时按钮禁用，界面不报错。
- [ ] 既有查找（Enter 循环、计数、全部替换）不回归。
