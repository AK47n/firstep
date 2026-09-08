# 01 — zigbee_link 双平台驱动落地（核心模块）

**要做什么：** 库内有 `zigbee_link` 模块（stm32 + mspm0）：manifest（简介/依赖/引脚/平台条目）就位，`zigbee_link_init / zigbee_link_send / zigbee_link_recv / zigbee_link_available` 全链路可用，接收走 ZIGBEE_UART 中断字节状态机 + 帧队列；stm32 单选生成通过全部静态门禁，mspm0 侧 syscfg 共享实例与协议形状测试全绿。用户可以在项目里勾选 `zigbee_link` 做双机/双车无线数据收发。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**评审整改（2026-09-05）：** 双轴评审发现并修复两处——① `zigbee_link_recv` 出队误读 `q_tail`（应为 `q_head`，队列永远取不到帧的严重缺陷），改 q_head 出队 + 截断路径统一按整帧取走（剩余载荷丢弃）计数；② `rx_sum`/`q_head` 死变量清理（q_head 修复后成为出队指针）；③ spec 要求「协议互不兼容注明」补进双平台 notes 与 .h 头注释。C 驱动无执行接缝（仓库惯例：协议逻辑不设 Python 执行单测，编译矩阵归手工验收），逻辑正确性以代码走查 + 本票测试断言为准。

- [x] `library/modules/zigbee_link/` 下 manifest.json + 双平台 code 文件存在，manifest 平台条目 / pins / 依赖形状正确（与 zigbee_uart 惯例一致，ZIGBEE_UART 宏、PB10/PB11、PA26/PA25）
- [x] stm32 版本：zigbee_link_init 走 uart_pin_init_ex 复位状态机；send 阻塞发 AA 55 LEN PAYLOAD SUM；RX 状态机校验 SUM 后入帧队列；定义 zigbee_rx_handler（复用母版 USART3_IRQ_CALLS 分发）
- [x] mspm0 版本：API 与 stm32 同形；init 开 ZIGBEE_UART NVIC；定义 ZIGBEE_UART_INST_IRQHandler；TX 走 DL_UART_transmitDataBlocking
- [x] syscfg_instances.INSTANCE_CONSUMERS["ZIGBEE_UART"] 增加 zigbee_link（单独选中保留实例）
- [x] 库级不变量绿：无题词（module universality）、无跨模块重复文件路径、mspm0 协议形状测试（新增 zigbee_link 用例）
- [x] stm32 单选生成（真实库 + 真实母版）全静态门禁通过、模块文件落盘、uvprojx 注册
- [x] 全量 pytest（本票涉及文件）绿
