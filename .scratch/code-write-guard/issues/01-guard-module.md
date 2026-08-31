# 01 — 写盘守卫模块 + 纯件 + 计数导出

**要做什么：** fx/write-guard.js 纯件（writeGuardNeeded 判定 / writeGuardTitle / writeGuardMessage 文案）+ ui/code-write-guard.js 的 guardCodeTabWrite(actionLabel)（条件满足弹两键 confirmModal，确认 → saveAllDirtyTabs，取消/失败 → false）+ ui/codeeditor.js 导出 dirtySavableTabCount()。

**被谁阻塞：** 无——可立即开始（依赖 code-tab-compile/02 的 saveAllDirtyTabs / dirtySavableTabs，已落地）。

**状态：** resolved

- [x] 验收 1：writeGuardNeeded(isContextDir, dirtyCount)——仅 isContextDir 且 count>0 时 true，其余 false（含 null/0）。
- [x] 验收 2：writeGuardMessage(actionLabel, dirtyCount) 含动作名与 N 个文件；writeGuardTitle 固定中文标题。
- [x] 验收 3：guardCodeTabWrite——不满足条件直通 true 零弹窗；满足时弹模态（confirmText「保存全部并继续」/cancelText「取消」）；确认后保存成功 → true + 脏点清除；保存取消 → false + 脏点保留 + toast；模态取消 → false。
- [x] 验收 4：dirtySavableTabCount 与 saveAllDirtyTabs 同判据（脏且非只读计数；0 时无脏）。
- [x] 验收 5：node 测试（write-guard.test.mjs + codeeditor.test.mjs 扩展）全绿；fx-guard 登记 write-guard.js。

**结论（2026-08-31）：** 全部落地并提交。评审整改：①fx/write-guard.js 增 WRITE_GUARD_ACTIONS 冻结枚举（写盘动作名单源，替代散落 5 模块裸字符串），window 桥随窗口导出；②write-guard.test.mjs 增 WRITE_GUARD_ACTIONS 键/值/冻结断言，fx-guard DOMAINS 登记 WRITE_GUARD_ACTIONS:'object'。说明：验收 5 中 codeeditor.test.mjs 未新增 dirtySavableTabCount 单测——ui/codeeditor.js 依赖 app.js 的 DOM 初始化（node 无法 import），该计数改由 CDP 冒烟断言覆盖（脏点计数 == 1 与保存后 == 0）；node 全量 1006 全绿、pytest 3049 全绿、code-write-guard 冒烟 11 项 PASS（含评审整改补的非上下文直通用例）。
