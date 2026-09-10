# 01 — 未保存退出保护

**要做什么：** 切换工程目录（打开另一目录）前若存在脏标签，弹确认模态三选：保存全部并切换 / 放弃修改并切换 / 取消；任意时刻存在脏标签时，页面刷新/关闭触发浏览器原生 beforeunload 提醒，防止未保存编辑静默丢失。保存中/程序化自动保存不误触发拦截。

**被谁阻塞：** 无。

**Type:** task
**Status:** resolved

## Answer

已实现并验证（提交 438b3794，CHANGELOG 自动 c3247021）：

- 纯件 fx/exit-guard.js：unsavedSwitchMessage / unsavedSwitchModalHTML（ESC 转义、清单截断 8 条、三动作按钮），单测 tests/js/exit-guard.test.mjs 5/5；
- ui/codeeditor.js：setCodeDir 异步化（脏标签 → 三选模态：保存全部并切换=saveAllDirtyTabs 复用（取消/失败中止切换）/ 放弃并切换 / 取消=不切换）；beforeunload 脏标签拦截（判据动态求值，无状态维护）；showUnsavedSwitchModal 接线对齐 conflictModal 先例（Esc/×/遮罩=取消、Tab 焦点陷阱、焦点归还、settled 防重入）；
- ui/codeview.js：loadCodeDir await setCodeDir，false 早退（网络请求在确认之后）；
- 审核整改：opts.force 死参数删除；脏判据工单文案对齐 dirtySavableTabs 单源（content 判据 + 理由：mtime 过期但内容一致≠有未保存编辑）；
- 验证：CDP 冒烟 smoke-01 13/13 PASS（三选/取消保编辑/放弃丢弃/保存写盘后重开一致/无脏直通/beforeunload 脏拦截·干净放行）；全量 node --test 1210 pass；pytest 3159 pass；双轴 code-review（Standards 硬违规 0、Spec 核心缺失 0）。

## 实现要点

- 目录切换入口（loadCodeDir / setCodeDir 路径）前置脏检查：收集脏标签（判据 = fx/codeeditor.js `dirtySavableTabs` 单源：内容 ≠ savedContent 且非只读——mtime 过期但内容一致 = 无未保存用户编辑，切换不丢工作，磁盘变更感知由基线流程负责，不列入），无脏直接走原逻辑；有脏弹三选确认模态。
- 「保存全部」= 复用 saveAllDirtyTabs（任一取消即中止，不切换）；「放弃修改」= 清空标签后切换；「取消」= 不切换。
- beforeunload：window 监听，存在脏标签时 preventDefault + returnValue 设置（浏览器展示原生提示，文案不可定制）；保存完成且无脏时自然不再拦截。
- 与既有「关闭脏标签确认」语义一致；不改变编辑器、编译、AI 既有行为。

## 验收 checklist

- [x] 打开 A 目录编辑不保存 → 切 B 目录 → 弹三选；「保存全部」切换后 A 修改已写盘；「放弃」切换且修改丢弃；「取消」不切换。
- [x] 有脏标签刷新页面 → 浏览器离开确认出现；全部保存后刷新 → 无确认。
- [x] 无脏标签切目录 → 直接切换不弹窗（无回归）。
- [x] 新建/编译自动保存不受影响；node 单测覆盖脏收集/判定纯件；CDP 冒烟 smoke-01 验证切目录三选与常规流。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
- 2026-09-10 第十轮：`smoke-01` 场景 5 的偶发**定性完成**——签名的「无活动标签」是**真产品缺陷**
  （`ui/codeview.js` `loadCodeDir` 的目录加载竞态：晚到的旧目录响应覆盖新目录清单），
  修复 + 确定性复现 + 守卫全部落在新单
  `.scratch/code-editor-refine/issues/12-save-switch-flake-diagnosis.md`。
  本单 checklist 无需改动（本单验的是「未保存退出保护」本身，第十轮复跑仍全绿）。
  本轮同时把 `smoke-01` 加固：`setText` 先等 textarea 到场并**回报是否写成**、
  场景 5 前加 7 个前置断点（`5-pre`~`5-pre5`，断言数 13 → 20），
  使「更早一步失败被后续断言掩盖」不再发生。
