# 工程说明

## 工程概览

- 平台：STM32F103C8T6 / Keil5
- 开发板：STM32F103C8T6 最小系统板（蓝药丸）

## 目录结构

| 目录/文件 | 用途 |
|---|---|
| `modules/` | 选中模块的驱动源码（每个模块一个子目录：.c/.h，已自动加入 Keil 工程与生成器的编译验证） |
| `user/` | Keil 工程：双击 Project.uvprojx 打开；编译产物在 user/Objects/（.hex 可烧录固件） |
| `sys/` | 内核与寄存器相关头文件（STM32 头文件 / CMSIS 内核定义）——无需改动 |
| `ml_libs/` | 板级基础驱动库（延时 / GPIO / 串口 / ADC 等 ml_* 实现与头文件）——按需调用 |
| `key/` | 启动文件（startup_*.s：复位入口与中断向量表）——无需改动 |
| `code/` | 母版自带的预留目录（仅一个说明文件）——本工具生成的模块代码在 modules/、主程序在根目录 main.c，此目录不需要动 |
| `main.c` | 主程序骨架——赛题逻辑从这里开始（第 8 步骨架、第 11 步任务推进逐步写入） |
| `pin_config.h` | 板级引脚配置（第 7 步「引脚配置」写入，与实际接线一一对应） |
| `isr.c` | 中断服务函数聚合文件（定时器 / 串口等中断逻辑——需要改中断处理时在这里） |
| `led_instances.h` | LED 多实例定义（第 6 步多实例配置写入——改灯名 / 灯数在这里对应） |
| `README.md` | 本工程说明——目录 / 编译烧录 / 接线 / 验证顺序与「生成后怎么继续」 |
| `演示脚本.md` | 演示流程（按评分点 / 功能需求组织）——答辩演示前看它 |
| `设计报告草稿.md` | 设计报告草稿（可选：AI 方案论证 + 软件流程，供报告参考；未生成 = 正常） |
| `main.py` | K230 / 视觉副产物（可选：选了带 Python 副产物的模块时生成，拷入 SD 卡使用） |
| `mp_deployment_source/` | K230 AI 模型部署包（可选：选了带 AI 模型的模板时生成——部署配置 + .kmodel，连同 main.py 一起拷入 SD 卡 /sdcard/） |
| `.contest_context.json` | 工具上下文清单（本次生成的输入快照——「修订与深化」回读用，勿手改） |
| `.contest_wiring.json` | 接线快照（工具绘制接线图用——勿手改） |

> 本工程由电赛工程生成器构建：main.c 是可编译的骨架/模板，含模块初始化与占位逻辑（TODO 标记）。赛题的实现逻辑需要你核对、补全并上板调试；引脚一致性以 pin_config.h 为准（与实际接线不一致先改这里）。

## 快速上手：编译 + 烧录

用 Keil MDK（uVision5）打开工程：双击 user/Project.uvprojx
编译：点击 Build（Project → Build Target，或按 F7）生成可烧录固件
烧录：接好 ST-Link，点击 Download（或按 F8）下载到 STM32F103C8T6

## 引脚接线表

| 模块 | 角色 | 引脚 | 说明 |
|---|---|---|---|
| config | LED_RED | PC13 | gpio_out |
| config | LED_YELLOW | PC14 | gpio_out |
| config | LED_GREEN | PC15 | gpio_out |
| config | BUZZER | PA15 | gpio_out |
| config | DIP0 | PB12 | gpio_in |
| config | DIP1 | PB13 | gpio_in |
| config | DIP2 | PB14 | gpio_in |
| config | DIP3 | PB15 | gpio_in |
| zigbee_uart_key | ZIGBEE_UART_TX | PB10 | uart_tx（必接） |
| zigbee_uart_key | ZIGBEE_UART_RX | PB11 | uart_rx（必接） |
| zigbee_link | ZIGBEE_UART_TX | PB10 | uart_tx（必接） |
| zigbee_link | ZIGBEE_UART_RX | PB11 | uart_rx（必接） |
| uwb_uart | UWB_UART_TX | PA9 | uart_tx（必接） |
| uwb_uart | UWB_UART_RX | PA10 | uart_rx（必接） |
| oled | OLED_SCL | PB8 | i2c_scl（必接） |
| oled | OLED_SDA | PB9 | i2c_sda（必接） |
| oled | OLED_SPI_SCL | PB4 | gpio_out（必接） |
| oled | OLED_SPI_SDA | PB5 | gpio_out（必接） |
| oled | OLED_SPI_DC | PB6 | gpio_out（必接） |
| oled | OLED_SPI_CS | PB7 | gpio_out（必接） |
| oled | OLED_SPI_RES | PA5 | gpio_out（必接） |
| beep | BUZZER_OUT | PA15 | gpio_out（必接） |
| relay | RELAY_OUT | PB4 | gpio_out（必接） |
| key | KEY_START | PB3 | gpio_in（必接） |

> 其余外设引脚以工程内 pin_config.h（stm32）/ mspm0.syscfg 为准

## 模块清单与依赖

- config：集中外设配置头文件：硬件引脚映射（UART/GPIO/LED/蜂鸣器/DIP 拨码）与通用显示、滤波参数统一集中定义，供各模块与主程序统一调用；适用于 UWB 定位、OLED 显示、LED/蜂鸣器指示等多外设联调场景。
- zigbee_uart_key：Zigbee DL-20 无线发射驱动：按固定帧格式（同步头 + ID + 校验和）组帧并上报本地 DIP-4 ID；适用于无线身份识别、无线信标上报等一对多收发赛题功能的发送侧。（依赖：config）
- zigbee_link：Zigbee DL-20 串口透传无线链路驱动（双平台）：长度前缀帧协议（同步头 + 长度 + 负载 + 校验和）任意字节收发，zigbee_link_send / zigbee_link_recv 轮询接口 + 接收帧队列；适用于双机/双车无线数据通信、遥控指令、遥测上报等需要无线传数据的赛题功能。（依赖：config）
- filter：实现基于环形缓冲区的滑动平均滤波器，用于平滑 UWB 距离和方位角等传感器数据、减少抖动；滤波逻辑通用，可复用于任意滑动平均场景。纯逻辑模块，无硬件绑定。
- uwb_uart：UWB 定位模块串口驱动：帧同步接收、XOR 校验、大小端解析，对距离和方位角做滑动平均滤波与野值钳位，输出原始与滤波后的定位数据。（依赖：config、filter）
- delay：MSPM0 毫秒延时：delay_ms 基于 CPUCLK_FREQ 换算调用 delay_cycles，任何时钟频率自动适配。
- oled：0.96 寸 OLED（SSD1306）显示驱动：I2C 硬件总线（默认，OLED_Init）与 SPI 总线变体（批次 12/07 决策 B——软 SPI 位操作 5 脚 SCL/SDA/DC/CS/RES、OLED_SPI_Init，适配 0.96 SPI 单色屏），显存式绘图（画点/字符/字符串/汉字，支持反色与 180° 旋转），带 16×8 ASCII 字库；分辨率支持 128×64（默认）与 128×32（0.91 寸，oled_set_res）。（依赖：delay）（来源：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/screen/0-96-iic-single-screen.html）
- led：LED 指示灯驱动（双平台）：led_init/led_on/led_off/led_toggle + 通道宏 LED_RED/LED_YELLOW/LED_GREEN；拉电流 1=亮 细节已封装在模块内。
- beep：蜂鸣器驱动（双平台）：beep_init/beep_on/beep_off/beep_toggle + beep_beep 响 N 声（阻塞式）。
- led_beep：声光组合模块（双平台）：LED + 蜂鸣器同时开关 + led_beep_alarm 声光报警；只控制一方请选 led 或 beep。（依赖：led、beep、delay）
- relay：1 路 5V 继电器模块驱动（mspm0 纯驱动切片，ADR 0009）：GPIO 输出（1 脚，光耦隔离/低电平吸合——低压控制高压），relay_init 初始断开 + relay_set(1=吸合/0=断开)；适用于继电器通断控制、火警联动断电、电灯/高压负载开关、自动浇花水泵等赛题功能。（来源：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/relay-module.html）
- key：按键读取（双平台）：get_key_state(channel) 按通道读取（上拉低电平按下）；多实例 = 多路独立按键（内置变体 start/stop/mode/set）；stm32 默认 PB3（JTDO 复位后可用），mspm0 默认 PA2。

## 第三方素材来源

本工程的部分模块驱动改写自立创开发板技术文档中心（wiki.lckfb.com）「地猛星 MSPM0G3507 模块移植手册」（清单行已附原页链接）。立创官网版权声明第三条要求：

> 请大家务必尊重贡献者的智力劳动成果：任何使用该文件的个人或组织，如需使用或者参考手册中的模块资料，将其复制、传播、修改、公开展示或在其他网站上使用，都需要在使用时清楚的标明文件的来源以及链接。

来源：https://wiki.lckfb.com/zh-hans/dmx/

## 验证顺序清单

按顺序逐个验证，前一个过了再接下一个

- [ ] delay — MSPM0 毫秒延时：delay_ms 基于 CPUCLK_FREQ 换算调用 delay_cycles，任何时钟频率自动适配。
- [ ] led — LED 指示灯驱动（双平台）：led_init/led_on/led_off/led_toggle + 通道宏 LED_RED/LED_YELLOW/LED_GREEN；拉电流 1=亮 细节已封装在模块内。
- [ ] led_beep — 声光组合模块（双平台）：LED + 蜂鸣器同时开关 + led_beep_alarm 声光报警；只控制一方请选 led 或 beep。
- [ ] config — 集中外设配置头文件：硬件引脚映射（UART/GPIO/LED/蜂鸣器/DIP 拨码）与通用显示、滤波参数统一集中定义，供各模块与主程序统一调用；适用于 UWB 定位、OLED 显示、LED/蜂鸣器指示等多外设联调场景。
- [ ] zigbee_uart_key — Zigbee DL-20 无线发射驱动：按固定帧格式（同步头 + ID + 校验和）组帧并上报本地 DIP-4 ID；适用于无线身份识别、无线信标上报等一对多收发赛题功能的发送侧。
- [ ] zigbee_link — Zigbee DL-20 串口透传无线链路驱动（双平台）：长度前缀帧协议（同步头 + 长度 + 负载 + 校验和）任意字节收发，zigbee_link_send / zigbee_link_recv 轮询接口 + 接收帧队列；适用于双机/双车无线数据通信、遥控指令、遥测上报等需要无线传数据的赛题功能。
- [ ] filter — 实现基于环形缓冲区的滑动平均滤波器，用于平滑 UWB 距离和方位角等传感器数据、减少抖动；滤波逻辑通用，可复用于任意滑动平均场景。纯逻辑模块，无硬件绑定。
- [ ] uwb_uart — UWB 定位模块串口驱动：帧同步接收、XOR 校验、大小端解析，对距离和方位角做滑动平均滤波与野值钳位，输出原始与滤波后的定位数据。
- [ ] oled — 0.96 寸 OLED（SSD1306）显示驱动：I2C 硬件总线（默认，OLED_Init）与 SPI 总线变体（批次 12/07 决策 B——软 SPI 位操作 5 脚 SCL/SDA/DC/CS/RES、OLED_SPI_Init，适配 0.96 SPI 单色屏），显存式绘图（画点/字符/字符串/汉字，支持反色与 180° 旋转），带 16×8 ASCII 字库；分辨率支持 128×64（默认）与 128×32（0.91 寸，oled_set_res）。
- [ ] beep — 蜂鸣器驱动（双平台）：beep_init/beep_on/beep_off/beep_toggle + beep_beep 响 N 声（阻塞式）。
- [ ] relay — 1 路 5V 继电器模块驱动（mspm0 纯驱动切片，ADR 0009）：GPIO 输出（1 脚，光耦隔离/低电平吸合——低压控制高压），relay_init 初始断开 + relay_set(1=吸合/0=断开)；适用于继电器通断控制、火警联动断电、电灯/高压负载开关、自动浇花水泵等赛题功能。
- [ ] key — 按键读取（双平台）：get_key_state(channel) 按通道读取（上拉低电平按下）；多实例 = 多路独立按键（内置变体 start/stop/mode/set）；stm32 默认 PB3（JTDO 复位后可用），mspm0 默认 PA2。

## 生成后怎么继续

回到工具的生成页，按需继续：

- 第 10 步「修复中心」：编译报错时看错误、让 AI 自动修复（工具内即可完成，不依赖外部 IDE）；
- 第 11 步「修订与深化」——赛题逻辑在这里写，主路径是**任务推进**：AI 按功能拆成有序任务卡，逐卡「做这一步」实现并立即编译验证，每步过后有 AI 的下一步指引（含接线 / 上板）；任务卡上可「和 AI 商量」、可「上板反馈」、可「烧录到板子」。同一页签还有：
  - **修订**：赛题答疑（Q&A）有增补时重新分析并覆盖式重生成（可回滚）；
  - **参数速调**：扫描可调参数（阈值 / 速度 / 频率…），改一个数即自动编译验证，可恢复旧值；
  - **交付**：检查未完成步骤、打包交付物（zip 自动排除 .contest_* 内部状态文件）；
  - **新想法 / 全局商量**：单个新想法直接修正落地，或与 AI 连续讨论整体方案（讨论可转任务 / 修正 / 采纳为全局结论）；
- 第 12 步「交接提示词」（可选）：把本次生成上下文打包成一段话，复制给外部 AI。

`.contest_*` 开头的文件（如 .contest_context.json / .contest_wiring.json / .contest_tasks.json）是工具的内部状态，随生成与每次执行自动更新——请勿手动编辑。
