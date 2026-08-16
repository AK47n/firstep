# 08 — zigbee_uart_key 补 mspm0（UART3 发送侧协议驱动）

**What to build:** zigbee_uart_key 新增 mspm0 版（与 zigbee_uart 共享 ZIGBEE_UART/UART3 实例与 PA26/PA25 默认脚，对偶 stm32 共享 ZIGBEE_* 宏先例）：DL_UART_transmitDataBlocking 组 4 字节身份帧，API 与 stm32 版同名同形（zigbee_uart_key_init/zigbee_uart_key_send_id）；key 侧不开 NVIC（只发不收），模块不定义 IRQHandler（与接收侧同选时由 zigbee_uart_mspm0.c 定义）。syscfg 实例映射补 zigbee_uart_key 为 ZIGBEE_UART 第二消费方（任一选中即保留实例）。

**Blocked by:** 07

**Status:** resolved（2026-08-15）

- [x] `code/zigbee_uart_key_mspm0.c/h`：DL_UART 阻塞发送四字节帧；不定义 IRQHandler
- [x] zigbee_uart_key manifest 补 mspm0 条目：files/pins（ZIGBEE_UART_TX/RX）/notes
- [x] syscfg_instances 映射补 ZIGBEE_UART 第二消费方 zigbee_uart_key
- [x] 测试：key 发送 API 双平台同形 + 共享实例映射（key 单独选中实例也保留）
- [x] 真机 mspm0 gmake 0 错（zigbee_uart_key + config；与接收侧同选也 0 错）
- [x] pytest 全绿 + mypy src 干净


## Comments

- 共享实例语义与 stm32 完全对偶：ZIGBEE_UART 一个 SysConfig 实例，接收侧开 NVIC + 定义 IRQHandler，发送侧只调 transmitDataBlocking；key 单独选中时 prune 也保留实例。
- 真机验收：`python .scratch/module-functionalize/verify_protocol_mspm0.py key` → gmake exit=0，0 error / 1 warning；日志 `.scratch/module-functionalize/out_key_mspm0/gmake_build.log`。