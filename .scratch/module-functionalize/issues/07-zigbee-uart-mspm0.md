# 07 — zigbee_uart 补 mspm0（UART3 接收侧协议驱动）

**What to build:** zigbee_uart 新增 mspm0 版（ZIGBEE_UART/UART3、PA26(TX)/PA25(RX)、115200、RX 中断）：DL-20 4 字节身份帧（AA 55 ID SUM）字节状态机，API 与 stm32 版同名同形（zigbee_uart_init/zigbee_rx_handler + g_key_id/g_key_id_updated/g_key_id_last_tick/g_zigbee_byte_count）；模块内定义 ZIGBEE_UART_INST_IRQHandler。母版 syscfg 增 ZIGBEE_UART 实例；syscfg 实例映射补 zigbee_uart 消费。

**Blocked by:** 06

**Status:** resolved（2026-08-15）

- [x] `code/zigbee_uart_mspm0.c/h`：DL_UART 字节级状态机（与 stm32 同帧格式/校验）
- [x] 母版 mspm0.syscfg 增 ZIGBEE_UART（UART3, PA26 TX / PA25 RX）；syscfg_instances 映射补 ("ZIGBEE_UART", ("zigbee_uart",))
- [x] zigbee_uart manifest 补 mspm0 条目：files/pins（ZIGBEE_UART_TX/RX）/notes
- [x] 测试：Zigbee 接收 API 双平台同形 + pins/syscfg 一致 + 裁剪映射
- [x] 真机 mspm0 gmake 0 错（zigbee_uart + config）
- [x] pytest 全绿 + mypy src 干净


## Comments

- 实例选择：UART3 排针 TX 有 PA26/PB2/PA14——选 PA26/PA25 避开 OLED I2C1 默认脚（PB2/PB3）与 STEP_MOTOR/DCC 输出（PA14/PA13），2026C 门锁套装默认可编译；与 HUIDU R2/R3 的默认重叠由「未选即裁剪 + 用户改绑」消解。
- ZIGBEE_UART 消费方暂只录 zigbee_uart，key 工单 08 补第二消费方（同一实例共享）。
- 真机验收：`python .scratch/module-functionalize/verify_protocol_mspm0.py zigbee` → gmake exit=0，0 error / 1 warning；日志 `.scratch/module-functionalize/out_zigbee_mspm0/gmake_build.log`。