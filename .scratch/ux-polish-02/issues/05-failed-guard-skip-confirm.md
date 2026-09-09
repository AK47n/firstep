# 05 — 失败卡防误标 + 跳过确认 + 动作措辞统一

**要做什么：** 编译失败（failed）的卡目前仍显示「确认通过」，可把红卡误标成已验证，污染进度与交付检查。修复：failed 状态去掉「确认通过」动作（只保留做这一步/回滚恢复）；「跳过」加确认弹窗并提示依赖连锁与恢复入口；跳过/恢复/重做三类按钮文案与悬停说明统一。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实现记录：** fx/task.js taskCardActions failed → ["run","revert"]（去掉 mark；
unverified 保留 mark＝上板人工确认）；generate-tasks.js skip 走 confirmModal（文案
点名依赖连锁与恢复入口，cancel 不落盘）；revert/skip/mark/redo 按钮补 title 并统一
措辞（skipped→「恢复此步」、其余→「重做」）；task.test.mjs failed 断言更新；
handoff-note-guard.test.mjs 对 goto-tasks 守卫断言对齐 ux-polish-02/04（async +
reviseLoad）。CDP 冒烟 probe-t05.mjs 全 PASS（每次运行前重置临时任务清单）。

- [x] failed 卡不再渲染「确认通过」按钮；unverified 卡保留「确认通过」（上板人工确认语义不变）；verified 卡行为不变
- [x] 「跳过」点击弹确认框：说明后续依赖该步的卡可能受影响、可随时恢复；确认文案「跳过」、取消「取消」
- [x] 跳过确认后行为与现状一致（置 skipped，不计入完成）
- [x] 按钮措辞统一：skipped 卡「恢复此步」、其余「重做」，均带 title 说明语义（恢复=回到待做；重做=回待做重跑）；「重做此步」（清建议标记）保留并补 title
- [x] 任务卡动作集（front-end 判定）改动同步纯函数单测（failed 无 mark）


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
