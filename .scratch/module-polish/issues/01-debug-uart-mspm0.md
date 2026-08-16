# 01 — debug_uart 补 mspm0（DEBUG_UART/UART2/PA23/PA22）

**What to build:** mspm0 调试串口模块：新增母版 syscfg `DEBUG_UART`（UART2，PA23 TX / PA22 RX，115200，RX 中断），代码 API 与 stm32 同形（debug_uart_init / debug_uart_send / debug_uart_rx_handler / debug_cmd_poll + DEBUG_PRINTF），模块内定义 DEBUG_UART_INST_IRQHandler；debug_cmd_poll 在 mspm0 只回显命令（LED/蜂鸣器命令由 led/beep 模块承担，不拖依赖）。

**Blocked by:** 无

**Status:** resolved（2026-08-15）


## Comments

- DEBUG_UART 与 UWB_UART 默认同 UART2、TX 同 PA23：这是用户定的“随便用一个”方案，冲突靠未选裁剪/用户改绑消解，test_pin_bindings 白名单已记录。
- 真机：`python .scratch/module-functionalize/verify_protocol_mspm0.py debug` → gmake exit=0，0 error / 1 warning（syscfg ovsRate 基线）。
- [x] code/debug_uart_mspm0.c/h + manifest mspm0 条目（pins PA23/PA22）
- [x] 母版 syscfg DEBUG_UART 实例 + syscfg_instances 映射 + test_pins 默认表
- [x] 测试：双平台 API 同形 + syscfg 一致 + 裁剪映射
- [x] 真机 mspm0 gmake 0 错（debug_uart 单独）
- [x] pytest 全绿 + mypy src 干净

- 追加：DEBUG_UART 与 UWB_UART 同 PA23 TX 暴露 pinwriter 定位歧义，已修 `_mspm0_path_matches` 对 uart/i2c 外设角色按 slug 反查实例名（与 GPIO 组同款）。