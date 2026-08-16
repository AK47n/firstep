# 模块打磨批次：debug_uart mspm0 + OLED 共同 API + delay_us + 编译矩阵

## Problem Statement

模块能力盘点发现四个 P0/P1 缺口：mspm0 无 debug_uart 导致无 OLED 时冒烟无输出通道；oled 双平台签名体系不同导致学生无法写同一份显示代码；mspm0 delay 缺 delay_us；全库 verified 状态几乎全是 false，缺少逐模块逐平台编译留痕。

## Solution

1. `debug_uart` 补 mspm0：新增 `DEBUG_UART` syscfg 实例（UART2，PA23 TX / PA22 RX，RX 中断）；API 与 stm32 同形（init/send/rx_handler/cmd_poll + DEBUG_PRINTF），模块内定义 IRQHandler。
2. `oled` 增双平台共同小写 API：`oled_show_text(line, column, text)`、`oled_show_number(line, column, number, length)`、`oled_refresh()`；旧 OLED_* API 原样保留。stm32 侧落在内嵌母版 ml_oled。
3. `delay` mspm0 补 `delay_us`。
4. 全库编译矩阵：逐模块 × 已有平台生成最小工程真编译；0 error 为硬门槛，模块自身 warning 必须为 0，syscfg 基线 warning 记录；按日志刷新 manifest verified/notes。

## User Decisions（2026-08-15）

- debug_uart mspm0 = UART2/PA23/PA22；
- 姿态方案优先级：imu_uart > ml_mpu6050（ml_mpu6050 高层包装暂不做）；
- 编译矩阵 warning 口径：0 error 硬门槛；模块自身 warning=0；syscfg ovsRate 等基线 warning 允许并记录；
- OLED 共同 API 以新增小写层实现，旧 API 不动。

## Out of Scope

- ml_mpu6050 mspm0 高层包装；
- uwb↔filter 可选化、config 解耦、getter 全量化；
- 板级真机行为验证（仍为编译级）。
