# 工单 02：灵活修正前端（fx/task.js + ui/generate-tasks.js + index.html + 测试）

Status: resolved

## 目标

任务推进区顶部「💡 新想法 / 发现的问题」输入区 + 分析结果卡（分类徽章 / reply / 落地按钮）+ 受影响任务「⚠ 建议重做」徽章与一键重做。

## 交付

- fx/task.js：`ideaResultHTML(analysis)`（三种 kind 徽章 + reply + 按钮区：new_task→[生成任务]，direct_fix→[改动预览并执行]，discussion→[把建议变成任务/修正]）+ `taskNeedsRedoBadge(task)` + taskCardHTML 集成（卡头「⚠ 建议重做」徽章 + 操作行「重做此步」按钮）→ window 桥 + fx-guard 登记。
- ui/generate-tasks.js：tasks-box 顶部 idea 输入区渲染（textarea + 按钮 + busy 守卫 + 结果容器）；`tasksIdeaAnalyze`（SSE idea_analyzing→idea_result）；按钮委托（insert → tasksRender；fix → SSE 流程复用 compile/task_reporting 文案 → done 后 tasksRender + 结果面板 mainDiffHTML + 回滚按钮 + affected 徽章刷新；discussion 转换按钮 = 同一 insert/fix 后端）；跨簇重置时机清空。
- index.html：输入区 + `.idea-*` / `.task-redo-badge` CSS（warn 色，沿用变量）。
- tests/js：fx/task.js 渲染断言（三 kind / needs_redo 徽章 / 按钮显隐 / 转义）；fx-guard 登记；JS 全量绿。

## 验收

1. 输入区出现在任务推进卡顶部（不绑定单卡），提交后显示分析卡。
2. new_task 结果卡只有「生成任务」主按钮；点击后清单出现新卡（后端 insert）。
3. direct_fix 结果卡只有「改动预览并执行」主按钮；执行后结果面板显示 diff + 编译状态 + 回滚按钮；受影响卡出现「⚠ 建议重做」+「重做此步」。
4. discussion 结果卡显示 AI 建议 + 两个转换按钮（把建议变成任务 / 变成修正）。
5. 重做此步 = 重置 pending + 清 needs_redo，随后可点「做这一步」走既有闭环。
6. JS 全量绿 + fx-guard 登记一致。
