# 工单 03：文档回归（task-insight/03）

Status: resolved

## 目标

CONTEXT.md 补词条（Task.resources / StepReport.checklist / 资源总览 / 自检清单）
+ 全量回归 + 提交。

## 交付

- CONTEXT.md：任务推进词条行补「每任务资源标注 resources（拆解时 AI 给，落盘
  清单）+ 顶部资源总览（重复标黄提示）+ 步骤报告 checklist（上板自检清单，
  可勾选 localStorage 备忘，随轮次落盘）」；新增/更新对应 fx 名
  （taskResourcesHTML / resourcesOverviewHTML / taskChecklistHTML）。
- 全量回归：pytest（Remove-Item Env:FIRSTEP_LAUNCHER）+ JS + 语言检查全绿。
- 中文提交；spec/issues 随提。

## 验收

词条与代码一致 / 全量绿 / 工作树干净。
