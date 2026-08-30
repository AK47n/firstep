# 06 — 任务进度与完成引导（卡内进度 + 去交付 + 折叠态保留）

**要做什么：** 分钟级任务执行中，卡片只有「进行中」徽章、进度文案全在面板顶部单条状态行（用户滚动到别的卡就看不到）。修复三点：① 执行中的任务卡内显示 spinner + 当前阶段文案（实现/编译/修复/总结，随 SSE 事件更新）；② 全部任务进入终态后总览显示「全部完成」+「去交付」按钮（切到交付页签）；③ 任务网格重渲染时保留卡上 details（更多菜单/自检清单/本轮变化）的展开态。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实现记录：** fx/task.js 新增 taskPhaseHTML（doing 卡 spinner+阶段槽）、
tasksOverviewHTML 完成态「全部完成 🎉 + 去交付」按钮、taskDetailsSnapshot/
taskDetailsRestore（details 展开态快照/恢复纯函数）；generate-tasks.js：
tasksExecute 阶段文案双通道（顶部状态行 + 卡内槽）、tasksRender 渲染前后
快照/恢复、tasks-overview 委托点交付页签（直接点 revise-tabs 交付按钮，零
模块耦合）；index.html 补 .task-phase spinner 动画与完成行样式；task.test.mjs
+4 组单测、fx-guard 登记。CDP 冒烟 probe-t06.mjs 全 PASS（全部完成→去交付
切页签；doing 卡阶段槽；跳过重建后自检清单展开态保留——「更多菜单」会被
既有「点外部收起」委托收起，属预期行为，恢复价值在清单/本轮变化类 details）。

- [ ] doing 态任务卡渲染 spinner + 阶段文案槽，执行中阶段切换（task_executing/compile_start/fix_start/task_reporting 等）实时更新该槽
- [ ] 面板顶部单条状态行保留（汇总语义），执行结束后卡内槽清理
- [ ] 全部任务处于终态（verified/skipped 之外无其他状态）时，总览/状态行显示「全部完成」+「去交付」按钮
- [ ] 「去交付」点击切到交付页签（复用既有页签切换），无任务时按钮不出现
- [ ] 渲染重建后：卡上展开中的 details 保持展开（按任务 id 恢复），用户未展开的不误弹
- [ ] 新增纯函数单测：完成态判定（含 unverified/doing/failed/pending 不算完成）、折叠快照/恢复辅助
- [ ] 既有下一步引导（做完一步 → 下一卡提示）与完成引导不冲突

