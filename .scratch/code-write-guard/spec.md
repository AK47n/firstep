# 反向写盘保护（生成侧写盘前提示代码栏未保存修改）

> 会话/系列 slug：code-write-guard。立项：2026-08-31（用户拍板）：
> ①触发范围 = 全部 5 个写盘入口（一键编译修复 / 修订执行 / 深化 / 任务「做
> 这一步」/ 参数「改值并编译」——凡会写盘的动作一致拦截，仅当代码栏有脏标签
> 且目录 = 生成上下文时提示，不打扰）；②提示行为 = 两键模态
> 「保存全部并继续（默认）/ 取消」。

## 问题陈述

代码栏（code-tab-compile 已完成）可编辑后，生成页的服务端写盘动作（AI 修复 /
修订 / 深化 / 任务执行 / 参数改值）会改写磁盘上的工程文件。若用户在代码栏有
未保存编辑，这些动作写盘后，用户直到下次保存才会遇到 409 冲突（事后才发现，
编辑差点被覆盖）。本特性在写盘动作**发起前**做一层提示：代码栏有 N 个未保存
文件时，先问「保存全部并继续」还是「取消」。

## 方案

1. **守卫模块**：`ui/code-write-guard.js` 导出 `guardCodeTabWrite(actionLabel)`
   → `Promise<boolean>`：
   - 条件（同时满足才提示）：当前代码栏目录非空、等于生成上下文
     （`isMainCDiskDir()` 单源）、且 `dirtySavableTabCount() > 0`；
   - 满足 → `confirmModal`（title「代码栏有未保存修改」、message 中文说明
     「『<动作>』将写入磁盘，代码栏有 N 个文件未保存——建议先保存全部，
     以免磁盘被覆盖后还需处理冲突」、confirmText「保存全部并继续」、
     cancelText「取消」，焦点默认「取消」防误触）；
   - 确认 → `await saveAllDirtyTabs()`；保存被取消/失败 → `false`（动作中止，
     toast 中文）；保存成功 → `true`（动作继续，编辑全部落盘）；
   - 不满足条件 → `true`（直通，零打扰零弹窗）。
2. **接线 5 个入口**（在各动作函数**内部开头** await，而非包 click 监听器——
   继续修复 / 继续任务等复用路径同样被保护）：
   - `startFixCenter`（一键编译修复，`btn-fix-center`）；
   - `reviseApply`（执行修订写盘，`btn-revise-apply`）；
   - `reviseDeepen`（深化，`btn-revise-deepen`）；
   - 任务「做这一步」`taskRun`（`.btn-task-run` 事件委托）；
   - 参数「改值并编译」`paramsApply`（`.btn-params-apply` 事件委托）。
3. **纯件**：`fx/write-guard.js`：`writeGuardNeeded(isContextDir, dirtyCount)`（判定）、
   `writeGuardMessage(actionLabel, dirtyCount)`（文案）、`writeGuardTitle()`（标题）
   —— node 单测覆盖；fx-guard 登记。
4. **计数导出**：`ui/codeeditor.js` 新增导出 `dirtySavableTabCount()`（读私有
   tabs → `dirtySavableTabs(tabs).length`，与 saveAllDirtyTabs 同判据单源）。

## 用户故事

1. 作为在代码栏改代码的用户，我点「一键编译修复 / 修订 / 深化 / 做这一步 /
   改值并编译」时，若有未保存文件会先被提示，以便写盘动作不覆盖我还没来得及
   保存的编辑。
2. 作为确认继续的用户，我点「保存全部并继续」，动作接着走、编辑全部落盘。
3. 作为取消的用户，我点「取消」，动作中止，编辑保留在代码栏，可自行保存后再来。
4. 作为不想被骚扰的用户，代码栏无脏标签或目录不是生成上下文时，不弹任何窗。

## 实现决策

- guard 放 `ui/code-write-guard.js`（依赖 codeeditor 的 saveAllDirtyTabs /
  dirtySavableTabCount / getCodeDir 与 codeview 的 isMainCDiskDir 导出面）。
- 两键模态复用 `confirmModal`（confirmText/cancelText），不做三键模态。
- 接线放动作函数内部开头（不是包装 click）——`continueFixCenter` 等复用路径
  同步覆盖；只读动作（analyze / scan / plan / chat / 会话）不拦。
- 保存全部期间用户可取消（saveAllDirtyTabs → {ok:false}）→ 动作中止 + toast；
  目录切换 → saveAllDirtyTabs 已自保护 → 同样中止。
- 与 409 的关系：本特性是**事前**提示层；保存时 409 冲突模态仍是**事后**兜底
  层，两层并存不互斥。

## 测试决策

- node：`tests/js/write-guard.test.mjs`（needed 判定真/假、message 含动作名
  与 N 文件、title）；`tests/js/codeeditor.test.mjs` 扩 `dirtySavableTabCount`
  （0 / 只读跳过 / 计数正确）。
- CDP 冒烟：`.scratch/code-write-guard/smoke.mjs`——openCodeViewer + 动态
  import `setMainCDiskContext(dir)`（同目录）+ 打开文件改脏 →
  `guardCodeTabWrite('测试动作')` 弹确认 → 点「保存全部并继续」→ 保存落盘
  （fetch mock 计数）返回 true、脏点清除；取消路径返回 false、脏点保留；
  无脏直通 true。
- 回归：node 全量 + pytest 全量 + smoke-02~05 全绿。
- 提交/工单/CHANGELOG 中文。

## 范围外

- 三键模态（「直接继续不保存」）——两键已覆盖主路径。
- 服务端写盘钩子（在生成侧接口内检测）——前端触发点已足够覆盖用户可感知路径。
- 保存全部失败后的手动重试 UI（沿用既有冲突模态与 toast）。

## 补充说明

- 接线点随 UI 演进新增写盘入口时，应同步在动作函数开头加一行 guard（本期在
  5 个入口落位，作为模式先例）。
