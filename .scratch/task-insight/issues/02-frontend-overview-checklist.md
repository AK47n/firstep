# 工单 02：资源总览 + 自检清单前端（task-insight/02）

Status: resolved

## 目标

任务卡资源徽标 + 顶部资源总览（冲突标黄）+ 结果面板可勾选自检清单。

## 交付

- `fx/task.js`：taskResourcesHTML(task)（「资源：」+ chips，空 → ""）；
  resourcesOverviewHTML(plan)（聚合 plan.tasks[].resources → 每资源一行
  「资源名 | 用到任务 tN：标题」，≥2 任务 → .res-conflict 行「⚠ 多任务使用，
  上板前确认」；全部空 → ""）；taskChecklistHTML(iteration, key)（checkbox
  列表 .task-check-list，勾选态 localStorage firstep.checklist.v1.<key>，
  onchange 写盘；key = taskId+"/"+seq；空 → ""）；taskCardHTML 描述后插
  taskResourcesHTML（非空才渲染）；taskStepReportHTML/blocks 后（ui 层）
  渲染 checklist；window 桥 + fx-guard 登记 3 导出。
- `ui/generate-tasks.js`：tasksRender 渲染 #tasks-resources（resourcesOverviewHTML
  innerHTML + hidden toggle——紧跟 #tasks-overview）；结果面板
  tasksRenderResult 在步骤报告块后插 taskChecklistHTML(最新轮, taskId+"/"+seq)；
  跨簇两重置清容器。
- `index.html`：tasks-box 内 #tasks-resources 容器 + CSS（.res-chip/.res-row/
  .res-conflict/.task-check-list 等，用既有变量零硬编码色）。
- 测试：task.test.mjs（resources chips 渲染/空 / overview 聚合+冲突标黄+转义 /
  checklist 勾选读写 localStorage（jsdom 桩 localStorage）/卡集成）；fx-guard
  登记。
- JS 全量绿；探针（可选）。

## 验收

1. JS 全量绿 + fx-guard 过。
2. 旧清单（无 resources）/旧轮次（无 checklist）渲染不炸（空态隐藏）。
3. 双轴评审通过后提交。
