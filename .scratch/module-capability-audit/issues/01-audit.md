# 01 — 全库模块能力盘点（只读报告）

**What to build:** 用 audit.py 扫描 `library/modules/*`（manifest + 全部 .c/.h）与 stm32 母版内嵌头，生成 `report.md`：平台覆盖 / pins / deps / verified / hardware_bound 总表；双平台 API 集合差分类；常用函数缺口候选与优先级。

**Blocked by:** 无

**Status:** resolved（2026-08-15）

## Comments

- 数据由 `.scratch/module-capability-audit/audit.py` 生成，可重复运行；只读库。
- 关键发现：mspm0 条目 22 个仅 1 个 verified；双平台 API 差异集中在 delay/led/oled/motor/ml_mpu6050；单平台缺口 debug_uart(mspm0) 与 huidu/imu_uart/step_motor/xunji(stm32)。
- 下一步决策见 report.md §7（debug_uart 实例、oled 共同签名、ml_mpu6050 方向、编译矩阵口径）。

- [x] report.md 含全库模块 × 平台总表
- [x] 双平台 API 集合差（模块头 + 内嵌母版头）
- [x] 缺口候选按 P0/P1/P2 与建议动作列出，不实施
- [x] 不改任何 library/src/tests 代码
