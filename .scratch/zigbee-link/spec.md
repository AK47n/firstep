# 通用 Zigbee 无线数据链路模块（zigbee_link）——spec

## 问题陈述

用户（参赛学生/工具作者）在模块推荐链路里遇到：题面「两小车无线通信」这类**需要无线传数据**的需求，库内明明有 Zigbee（`zigbee_uart`/`zigbee_uart_key`），却显示「库内无命中」并落库外建议 NRF24L01（需自备）。根因：库内 Zigbee 实现是 2026C 门锁场景的**固定 DIP-4 ID 帧**专用驱动（`AA 55 ID SUM`，只做身份识别/信标上报），没有暴露通用双向数据收发能力；AI 实现覆盖检查按 manifest 简介判定「不覆盖两车无线通信」是合理结论。买件指引的词表「无线通信模块」组也没有任何方案挂 `lib_modules`，所以连「库内已有」徽标都看不到。

## 方案

新增一个**通用 Zigbee 无线数据链路模块 `zigbee_link`**：DL-20 是 ZigBee 串口**透明传输**模块（115200 点对点，发什么对端收什么，无需 AT 配置），在它之上实现长度前缀帧协议，提供任意字节收发 API（双平台 stm32/mspm0）。与既有 `zigbee_uart`（固定 ID 帧接收）走同一 `ZIGBEE_UART` 实例和中断入口，两者互斥（同一路 RX 只能有一个消费者），2026C 既有流程不受影响。词表「无线通信模块」补一条 Zigbee 方案并挂 `lib_modules`，买件指引显示「库内已有：zigbee_link」。

## 用户故事

1. 作为参赛学生，做两车/双机无线通信时，我希望推荐链路直接命中 `zigbee_link` 并可勾选进工程，而不是只能看到「需自备 NRF24L01」。
2. 作为参赛学生，用 `zigbee_link` 时，我能发送任意长度短帧（指令/状态，≤32 字节负载），并轮询收到对端发来的帧。
3. 作为参赛学生，stm32 与 mspm0 两条平台线都能用同一个 API。
4. 作为工具作者，2026C 数字钥匙既有流程（`zigbee_uart` + `zigbee_uart_key`）逐字节不变、照常可用。
5. 作为工具作者，买件指引的「无线通信模块」方案能看到「库内已有：zigbee_link」，避免用户重复采购。
6. 作为工具作者，新模块简介符合 ADR 0009（纯驱动、无题绑定），推荐链路自动可见。
7. 作为工具作者，`zigbee_link` 与 `zigbee_uart` 不会被同时选中（互斥组 UI + 生成门禁双保险），不会重演 UV4 L6200E multiply defined。

## 实现决策

- **模块**：`zigbee_link`，双平台（stm32/mspm0），依赖 `config`；文件名/符号全部独立（`zigbee_link.c/.h`、`zigbee_link_mspm0.c/.h`）。
- **硬件接缝**：沿用 `ZIGBEE_UART` 实例（stm32 UART_3 / PB10 TX / PB11 RX；mspm0 UART3 / PA26 TX / PA25 RX）与 `ZIGBEE_BAUD=115200`；引脚沿用 `ZIGBEE_UART_TX/RX` 宏，pins 声明与 `zigbee_uart` 同形。
- **帧协议**（与既有 ID 帧同风格、但校验包含长度，旧 ID 帧不会误判为合法帧）：
  `AA 55 LEN PAYLOAD[LEN] SUM`，`1 ≤ LEN ≤ 32`，`SUM = (0xAA + 0x55 + LEN + ΣPAYLOAD) & 0xFF`；双端必须同为 `zigbee_link`（与 2026C ID 帧协议互不兼容，README/简介注明）。
- **API 契约**（stm32/mspm0 同形）：
  - `void zigbee_link_init(void)` —— init 后开 RX 中断
  - `void zigbee_link_send(const uint8_t *payload, uint8_t len)` —— 阻塞发送一帧（len 1..32）
  - `uint8_t zigbee_link_recv(uint8_t *out, uint8_t max_len)` —— 非阻塞取一帧，返回帧长，0 = 无帧
  - `uint8_t zigbee_link_available(void)` —— 接收队列中完整帧数
  - 诊断全局量：`g_zigbee_link_frame_count` / `g_zigbee_link_byte_count`
  - RX 实现 = 中断字节状态机（对齐既有 zigbee 状态机风格）+ 帧队列（环形，容量 4 帧）
- **中断归属**：zigbee_link 是 `ZIGBEE_UART` 的接收消费者，与 `zigbee_uart` **互斥**：
  - manifest 新增 exclusive group（同 id/label、不同 role）：可建议 `id=zigbee-rx`、`label=Zigbee 无线链路（接收侧）`、`zigbee_uart.role=固定 DIP-4 ID 帧接收（身份识别/信标上报）`、`zigbee_link.role=任意字节帧收发（双机/双车无线数据通信）`
  - stm32 侧 zigbee_link 定义 `void zigbee_rx_handler(void)`（与 zigbee_uart 同名，复用母版 `USART3_IRQ_CALLS` 分发；互斥保证唯一定义）
  - mspm0 侧 zigbee_link 定义 `void ZIGBEE_UART_INST_IRQHandler(void)`（与 zigbee_uart 同惯例；互斥保证唯一定义）
  - `zigbee_uart_key`（只发不收、不定义 handler）不受互斥限制，可与任一侧配对
- **生成门禁**：`zigbee_uart` + `zigbee_link` 同选 → 生成 400 中文错误（明确「同一路 ZIGBEE_UART 只能选一个接收驱动」），与互斥组 UI 双保险；`zigbee_link` + `zigbee_uart_key` 同选 → 放行。
- **词表**：「无线通信模块」组新增方案 `Zigbee 模块（DL-20 串口透传）`：interface=UART 串口透传；note 注明库内已打通、全新 115200 点对点、程序不需 AT 配置；suitable=双机/双车无线数据通信/遥控遥测；`recommended` 不再设（该组已有 2 个 recommended，按「每类 ≤2」规则）；`lib_modules=["zigbee_link"]`。`Zigbee` 暂不加入 models（避免误导为库外建议名；由 LLM 覆盖检查直接命中真模块）。
- **简介**（ADR 0009 四要素、无题词）：Zigbee DL-20 串口透传无线链路驱动（双平台）：长度前缀帧协议任意字节收发（zigbee_link_send/zigbee_link_recv + RX 帧队列）；适用于双机/双车无线数据通信、遥控指令、遥测上报等需要无线传数据的赛题功能。
- **验证标记**：无工具链环境 → 平台条目 `verified=false`（未验证/未上板，按惯例走「未验证」平台警告，不假绿）。

## 测试决策

- **接缝选型**：沿用既有真实库 + 真实母版接缝——`tests/test_module_protocol_mspm0.py`（协议驱动形状/pins/实例映射先例）、`tests/test_module_collision.py`（单选生成 + 符号/文件唯一 + 双选门禁先例）、`tests/test_syscfg_prune.py`（INSTANCE_CONSUMERS 消费者）、`tests/test_pins.py` / `tests/test_default_layout.py`（ZIGBEE 引脚宏）、`tests/test_wordlist.py`（lib_modules 校验）、`tests/test_module_universality.py`（无题词 + 互斥组快照）、`tests/test_recommend_cache.py`/选择层（词表命中单源）。不新开测试文件层级。
- **必须断言**：
  - 真库扫描：`zigbee_link` 简介/代码无题词；与任何模块无重复平台文件路径；互斥组聚合快照（真库）更新为含 `zigbee-rx`。
  - mspm0：API 与 stm32 同形；`ZIGBEE_UART` 在 `INSTANCE_CONSUMERS["zigbee_link"]`；单独选中 syscfg 保留 ZIGBEE_UART；`ZIGBEE_UART_INST_IRQHandler` 只在 zigbee_link/zigbee_uart 中之一侧定义。
  - stm32：单选 `zigbee_link` 生成通过全部静态门禁；`zigbee_link`+`zigbee_uart` 同选 → 400；`zigbee_link`+`zigbee_uart_key` 同选 → 放行；uvprojx 注册文件路径正确。
  - 词表：新方案 `lib_modules` 引用存在 slug（加载即校验）；词表解析/方案数/徽标规则单测。
- **不做**：真机验证、编译矩阵（无 uv4/gmake/CCS 工具链）；LLM 覆盖检查结果类测试（非确定性，不设断言）。

## 范围外

- 不改 `zigbee_uart` / `zigbee_uart_key` 的任何现有文件、符号与行为（2026C 流程逐字节兼容）。
- 不做 Zigbee 与 NRF24L01/蓝牙/LoRa 的统一抽象层或互认协议。
- 不做 DL-20 的 AT 配置/信道切换/配对（模块按预配置 115200 点对点使用，程序不发包 AT）。
- 不做真机烧录验证与编译矩阵（环境无工具链）。
- 不改推荐链路 LLM 机制（覆盖检查仍由 AI 按简介判定；命中靠简介/词表可见性，不引入机械映射）。

## 补充说明

- 设计取舍说明：为何新模块而非扩展 zigbee_uart —— 2026C 用 `zigbee_uart`（收）+`zigbee_uart_key`（发）配对，若把通用收发塞进 zigbee_uart，会改变其符号/行为并影响既有流程；新模块 + 互斥组是零回归的最小路径。
- 为何互斥而非共存 —— UART3 只有一份 RX 数据寄存器，两个解析器无法同时消费；互斥组（UI 单选）+ 生成门禁（API 兜底）双保险，防 L6200E 重演。
- 验证方式：全量 pytest + js 测试绿；CLI/服务端手工跑 2021F 推荐需真实 LLM（费用自理），预期「句子83 两小车无线通信」由 NRF24L01 库外建议变为 zigbee_link 库内命中（LLM 非确定性，不能保证逐字）。
