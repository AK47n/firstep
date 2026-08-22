# 02 — 顶部进度条 + 完成计数

**要做什么：** header 下方一条 3px 青色渐变进度条 + 右端「已完成 n/12」计数，随步骤完成状态联动；进度 0 隐藏；切出生成页隐藏。

**被谁阻塞：** 无（与 01 独立）。

**状态：** resolved

- [x] 纯函数 `stepProgress(doneCount, total)` → `{ pct, text }`（total 非法兜底 12、越界裁剪、字符串数字可解析）
- [x] `stepDoneSet` 集合 + `syncStepDone` 挂在 markStepDone / markStepUndone 上；`renderStepProgress` 同步填充宽度与「已完成 n/12」文本，0 隐藏、>0 显示
- [x] tab 切换显隐：切出生成页隐藏，切回按完成数恢复
- [x] `tests/js/step-progress.test.mjs`：0/12、12/12、5/12（42%）、total 非法兜底、越界裁剪、字符串数字、NaN 共 7 个，全绿
- [x] CDP 状态机验证：初始 hidden → 4 步 33% → 12 步 100% → undo 92% → library 隐藏 → generate 恢复；截图目检（1/3 青填充 + 计数）通过
