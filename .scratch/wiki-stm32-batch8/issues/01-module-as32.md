# 01 — as32 433MHz LoRa 串口数传（UART 轮询透传，手册 rf--as32-lora-wireless-communication-module.md）

**要做什么：** 模块库 `as32` 新增 **stm32 平台条目**（mspm0 零改动）：F1 页串口数传驱动 → 纯驱动切片，API 与 mspm0 完全对齐（as32_init / as32_send_string / as32_send_hex / as32_receive（uint16_t 返回、读后清缓冲）/ as32_flush；AS32_RX_BUF_MAX 300u）。stm32 侧 = uart_pin_init_ex 参数化 UART + `uart_baud_config(..., 9600)` + **关闭 RXNEIE 轮询接收**（页面接收中断+空闲中断缓冲改轮询——mspm0 同判：与同实例 ZIGBEE 的 ISR 重复问题；SR/DR 直读排空 + cap 截断修正：页面 `(len+1)%MAX` 模运算满缓冲回绕覆盖首字节 → 满则丢新字节 + '\0' 收尾，notes）。

**关键事实（F1 页 + mspm0 库内）：** F1 页默认 = 串口2（PA2/PA3，9600）——DEBUG_UART 常备件不照抄。**UART 实例仲裁：默认 UART_3（ZIGBEE_UART 宿主）**——LoRa 与 Zigbee 无线数传**互替件**、同选概率最低（mspm0 定稿同款：默认挂 UART3、同选经绑定换实例）；默认 TX=PB10/RX=PB11（ZIGBEE_UART 原脚——互替件同脚先例；页边注：`_check_uart_instance_conflicts` 只查用户绑定，默认共享合法先例）。AT 配置范围外（页面无 AT 代码——notes 说明可经 as32_send_string 配置模式直发或上位机软件 soft_asds.zip 预设）。

**引脚：** pins `AS32_UART_TX`（uart_tx，PB10，macros `[AS32_UART, AS32_UART_INST, AS32_UART_TX_GPIO, AS32_UART_TX_Pin]`）+ `AS32_UART_RX`（uart_rx，PB11，macros `[AS32_UART_RX_GPIO, AS32_UART_RX_Pin]`）；pin_config.h 宏段 + USART3_IRQ_CALLS 不变（轮询件不进聚合表——pinwriter `_UART_CALLS_ROLES` 无 AS32 条目）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论回填（2026-09-07）：全部完成。stm32 条目 = UART 轮询透传件（F1 页 USART2 接收+空闲中断缓冲改 SR/DR 轮询排空——mspm0 同判：与同实例 zigbee 的 ISR 强符号/聚合重复问题；init 关 RXNEIE（CR1 bit5）断流）。API 与 mspm0 全对齐（as32_init/send_string/send_hex/receive/flush——as32.h 现名逐字对齐；AS32_RX_BUF_MAX 300u + 新增 AS32_BAUDRATE 9600）。**UART 实例仲裁 = UART_3（ZIGBEE_UART 宿主）**：LoRa 与 Zigbee 无线数传互替件、同选概率最低（mspm0 定稿同款）；默认 TX=PB10/RX=PB11（ZIGBEE_UART 原脚——互替件同脚先例）；**门禁口径确认：`_check_uart_instance_conflicts` 只查用户绑定——默认×默认共享合法先例**（as32×zigbee/键盘同脚登记 test_default_layout 白名单）；F1 页默认串口2（PA2/PA3）不照抄 = DEBUG_UART 常备件。**页面缺陷**：接收缓冲 `(len+1)%MAX` 模运算回绕覆盖首字节 → cap 截断 + '\0' 收尾；页面无 AT 代码——AT 配置范围外（notes 给配置模式直发/上位机 soft_asds.zip 预设路径）。**零改造点**：pinwriter `_UART_CALLS_ROLES` 无 AS32 条目（轮询件无 rx_handler、不进 isr.c 聚合；USART3_IRQ_CALLS 零变化——母版 isr.c 无需改）。**F1 换算**：USART_* → ml_uart（uart_pin_init_ex 参数化 + uart_baud_config 9600 + uart_sendbyte），RX 读 = `AS32_UART_INST->SR/DR`（coord_detect 先例），零引脚字面量；**NULL 未定义修复**（headfile.h 不含 stddef——ball-detect-null-fix/01 先例，补 `#include <stddef.h>`）。verified=true（UV4 0 error/0 module warning，2026-09-07，f8720f1e）+ kit/source_url（地阔星 wiki 原页）+ notes（手册路径/原页/厂家资料/9600/UART3 仲裁/互替件同脚/轮询+截断修正/AT 范围外/未上板）；wordlist 零补录（已挂接）；mspm0 零改动；description 双平台化。test_pins 宏表 +AS32 六宏、test_default_layout PB10/PB11 白名单 +as32（互替件同脚先例——分组断言同步）。

**实施清单：**
- [ ] `library/modules/as32/code/as32_stm32.c/.h`（轮询收发：uart_pin_init_ex + uart_baud_config 9600 + 关 RXNEIE；send 走 uart_sendbyte 忙等；receive 轮询 SR RXNE → DR → 缓冲 cap 截断）
- [ ] manifest.json platforms 增 stm32：files、dependencies []（mspm0 现状）、verified false、hardware_bound false、pins 2 行、kit/source_url（地阔星 wiki 原页）、notes（手册路径/原页/网盘 soft_asds.zip/采购/9600/UART3 仲裁/互替件同脚 + ZIGBEE 同实例默认共享先例/页面中断改轮询 + 截断修正/AT 范围外/未上板）
- [ ] pin_config.h 增 AS32 宏段；母版 isr.c 无需改（轮询）
- [ ] 测试 `tests/test_module_as32.py`（形状+宏存在+单选生成+mspm0 零改动+守卫：`AS32_RX_BUF_MAX 300u`、无 `IRQHandler`、无 `% AS32_RX_BUF_MAX`、9600、SR/DR 轮询）
- [ ] test_pins.py 补 6 宏；test_default_layout.py PB10/PB11 登记 as32
- [ ] UV4 矩阵 0/0（MAIN_C 调 init/send_string/send_hex/receive/flush (void) 化）→ verified=true
- [ ] wordlist 零补录复核；中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0；mspm0 零改动。
