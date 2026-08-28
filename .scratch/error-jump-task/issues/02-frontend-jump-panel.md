# 错误行跳转：前端迁移 + 任务结果面板集成（error-jump-task/02）

## 状态
Status: resolved

## 目标
maincScrollToRange / maincJumpToLine 从 ui/generate-fix.js 迁入 fx/code.js
（单源，任务面板与修复中心共用）；任务结果面板 failed 时渲染编译错误列表，
点击 main.c 错误行跳转高亮。

## 实现
- fx/code.js：迁入 `maincScrollToRange(ta, range)` 与
  `maincJumpToLine(line)`（返回 null 成功 / "empty" | "out-of-range" |
  "no-textarea" 错误码；toast 由调用方做）；`import { syncCollapseBtn } from
  "./generate.js"`（无环：generate.js 无共享件依赖）；window 桥补两导出；
  头注释补迁移说明。
- generate-fix.js：删私有两函数（import 改为从 fx/code.js 导入
  maincJumpToLine / maincLineOffsetRange / isMainCPath / maincContentEmpty）；
  fixToggleSource 的 main.c 分支改为按错误码 toast（三条消息逐字保留：
  「main.c 还没有内容，先「生成骨架」再跳转」/「行号超出 main.c 范围」/
  成功无提示）；头注释词表更新。
- fx/task.js：新 `taskErrorsHTML(parsedErrors)` 导出（.task-err-row 每行：
  path:line（isMainCPath(path) 且 line>0 时 .task-err-jump 可点 data-line）
  + message；全 esc；空数组/非数组 → ""）；window 桥 + fx-guard 登记。
- ui/generate-tasks.js：tasksRenderResult 在 `.reason`（markup.detail）后、
  stepReport 前插 `taskErrorsHTML(data.compile && data.compile.parsed_errors)`
  （渲染到 #tasks-result 内；委托在网格上 .task-err-jump click →
  maincJumpToLine(Number(el.dataset.line))，错误码 toast：
  empty → 「main.c 还没有内容…」、out-of-range → 「行号超出 main.c 范围」、
  no-textarea 静默）；头注释事件词表不变（无新事件）。
- tests：task.test.mjs（taskErrorsHTML 转义 / 非 main.c 无 data-line /
  空数组空串 / 可点行带 data-line）；fx-guard 登记 code.js 2 导出 +
  taskErrorsHTML；code.test.mjs 若存在则加 maincJumpToLine 错误码桩测试
  （无 DOM 时 no-textarea；jsdom 空 textarea empty 分支）——不存在则断言
  并入 task.test.mjs。

## 交付
- 双轴评审 → 整改 → JS 全量 → 提交。
