# 模块能力盘点——功能规格

## Problem Statement

模块库已经做到「依赖结构独立、协议模块双平台」，但缺少一张全局能力地图：哪些模块在哪些平台可用、验证状态如何、双平台 API 是否真的同名同形、还有哪些常用函数缺口。后续任何「模块功能拓展」都应基于这张图决策，而不是逐个模块零散猜。

## Solution

做一次**只读盘点**，产出 `.scratch/module-capability-audit/report.md`：

1. 全库模块 × 平台总表（files / pins / deps / verified / hardware_bound）；
2. 双平台 API 集合差（模块头 + stm32 内嵌母版头），按「一致 / 遗留兼容 / 平台有意差异 / 真正缺口」分类；
3. 常用函数候选缺口清单与建议优先级（不实施）。

## Out of Scope

- 不改任何 `library/modules/*`、`library/masters/*`、`src/*`、`tests/*`；
- 不做编译矩阵（盘点后另开工单）；
- 不实施 uwb↔filter 可选化、config 解耦、getter 全量化（已评审暂缓）。

## Testing Decisions

- 盘点结果以 markdown 报告为交付物；
- 数据由 `.scratch/module-capability-audit/audit.py` 可重复生成（只读库）。
