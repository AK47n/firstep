# 批次 8「无线/红外」— 立创 wiki 地阔星 STM32F103C8T6 手册模块批量入库（stm32 线）

## 问题陈述

stm32 线进度：批次 1-7 已入库 45 件（全部 0/0 矩阵）。本批 = **无线/红外六件**：as32（433MHz LoRa 串口数传）、hc05（蓝牙串口透传）、nrf24l01（2.4G 软 SPI 无线收发）、rc522（射频 IC 卡读卡，软 SPI）、ir_remote（红外遥控接收解码）、ir_remote_tx（红外编码发射）。六件**均已有 mspm0 条目**（A 类：mspm0 侧零改动），本批补 stm32 平台条目。重点：**UART 实例仲裁**（as32/hc05——stm32 现有 UART1/DIGIT+COORD+UWB、UART2/DEBUG、UART3/ZIGBEE 全占，默认实例与既有重叠按「同选概率最低」推理、同选经绑定消解；`_check_uart_instance_conflicts` 门禁只查用户绑定，默认共享为合法先例）与**软 SPI**（nrf24l01 六脚/rc522 五脚位操作，不占硬件 SPI/TIMER——照 max7219/lcd 软 SPI mspm0 先例，页面对应 F1 口径）。

## 方案

照批次 1-7 管线：页面取证（.scratch/`%TEMP%` batch-facts + 地阔星 F1 页）→ 纯驱动切片改造（去 main/printf、API 与 mspm0 `.h` 现名完全对齐）→ 母版 ml_* API 换算 → 母版 `pin_config.h` 新宏段（+ isr.c `__weak` 兜底 + pinwriter `_UART_CALLS_ROLES` 扩展——本批 UART 件首次进入 stm32 聚合面）→ manifest stm32 条目（files/pins+macros/verified 初 false/kit+source_url=地阔星 wiki 原页/notes 含手册路径+网盘+改造+修正）→ 测试（新增 test_module_<slug>.py 照 test_module_mq2.py 模板 + test_pins/test_default_layout 同步 + mspm0 零改动守卫）→ **UV4 单选编译矩阵 0 error/0 module warning**（`C:/Keil5/Core/UV4/UV4.exe`，`-j0 -r -b`）→ verified 回写 → 中文提交 → 工单 resolved。

## 用户故事

1. 做题用户选 stm32 + as32：`as32_init()` 后 `as32_send_string/send_hex` 发送、`as32_receive(buf, max)` 轮询收数（读后清缓冲）——远距双端遥控/遥测/组网，打开即编译（9600，默认 UART3/ZIGBEE 互替）。
2. 做题用户选 stm32 + hc05：`hc05_init()` 后 `hc05_send_*` 发送、`hc05_available/receive` 收数（RX 中断环形缓冲）、`hc05_is_connected` 读 STATE、`hc05_at_mode_enter/exit` 驱动 KEY——手机遥控/上位机无线通信。
3. 做题用户选 stm32 + nrf24l01：`nrf24l01_init` + `set_*` 配置 + `tx_packet/rx_packet` 收发——软 SPI 六脚位操作，不占硬件 SPI/TIMER。
4. 做题用户选 stm32 + rc522：`rc522_init` + `rc522_read_card` 出 4 字节 UID + `auth_block/read_block/write_block/halt`——读卡门禁/身份识别。
5. 做题用户选 stm32 + ir_remote / ir_remote_tx：`ir_remote_poll` 忙等解码 NEC 帧（get_address/get_code/has_data/clear）；`ir_tx_init` + `ir_tx_send/ir_tx_send_repeat` 发 38kHz NEC 帧——双机红外遥控，收发配对即插即用。
6. 维护者：每件可溯源（source_url=地阔星 wiki 原页、notes 含 F1 页面缺陷记录、未上板）。

## 实现决策

### 既定事实（勿重新调研；2026-09 已取证——地阔星 F1 页 + mspm0 库内现状读盘复核）

① **API 与 mspm0 `<slug>.h` 现名完全对齐**（读现名写，勿凭记忆；stm32 侧同函数名/同语义/同返回码）：

| slug | 头文件 API 现名（mspm0 → stm32 同名） | 常量 |
|---|---|---|
| as32 | `as32_init` / `as32_send_string(const char*)` / `as32_send_hex(const uint8_t*, uint16_t)` / `as32_receive(uint8_t*, uint16_t)→uint16_t`（读后清缓冲）/ `as32_flush` | `AS32_RX_BUF_MAX 300u` |
| hc05 | `hc05_init` / `hc05_send_char` / `hc05_send_string` / `hc05_send_buffer` / `hc05_available→uint16_t` / `hc05_receive(buf,max)→uint16_t` / `hc05_clear_rx` / `hc05_is_connected→uint8_t` / `hc05_at_mode_enter` / `hc05_at_mode_exit` | `HC05_RX_BUF_SIZE 128u`、`HC05_CONNECTED_LEVEL 1` |
| nrf24l01 | `nrf24l01_init` / `set_channel` / `set_speed` / `set_power` / `set_address` / `set_mode` / `tx_packet→uint8_t` / `rx_packet→uint8_t` / `flush_rx` / `flush_tx` | 枚举 `nrf24l01_mode_t/speed_t/power_t`、`NRF24L01_TX_OK 0x20`/`MAX_TX 0x10`/`RX_OK 0x40`/`TX_ERR 0xFF`、`PAYLOAD_MAX 32` |
| rc522 | `rc522_init` / `rc522_read_card(uint8_t uid[4])` / `rc522_auth_block` / `rc522_read_block` / `rc522_write_block` / `rc522_halt` | `RC522_OK 0x26`/`NOTAGERR 0xCC`/`ERR 0xBB`、`RC522_AUTH_KEYA 0x60`/`KEYB 0x61` |
| ir_remote | `ir_remote_init` / `ir_remote_poll→uint8_t`（1=新帧/2=重复码/0=超时无效）/ `ir_remote_get_address` / `ir_remote_get_code` / `ir_remote_has_data` / `ir_remote_clear` | （内部 20us 拍、阈值同 mspm0） |
| ir_remote_tx | `ir_tx_init` / `ir_tx_send(uint8_t address, uint8_t command)` / `ir_tx_send_repeat` | `IR_TX_FREQ_HZ 38000u`、`IR_TX_MSB_FIRST 1` |

② **stm32 UART 实例现状**（read 后写）：`UART_1`=DIGIT_UART+COORD_DETECT_UART+UWB_UART（PA9/PA10）、`UART_2`=DEBUG_UART（PA2/PA3）、`UART_3`=ZIGBEE_UART（PB10/PB11）——三实例全占；UART 角色绑定 = 类型级（TX/RX 对同实例），`_check_uart_instance_conflicts` 只查用户绑定（缺省/默认×默认不查——UWB/DIGIT/COORD 共 UART_1 现状合法先例）；UART 接收聚合 = 母版 isr.c `USARTx_IRQHandler` → pin_config.h `USARTx_IRQ_CALLS` 聚合宏（pinwriter `_UART_CALLS_ROLES` 表 + `_regroup_irq_calls` 按 `{STEM}_UART` 现值重分组 + 母版 `__weak` 空兜底）。

③ **F1 页面默认脚**（地阔星 dkx F1 页取证，全部与既有角色互抢、不作默认）：

| slug | F1 页默认 | stm32 现状 |
|---|---|---|
| as32 | 串口2 = PA2(TX)/PA3(RX)，9600；页面接收中断+空闲中断 | PA2/PA3 = DEBUG_UART 常备件（不照抄） |
| hc05 | 串口2 = PA2(TX)/PA3(RX)，115200（代码）；STATE = PA7 输入；页面无 KEY 引脚驱动 | PA2/PA3 = DEBUG_UART；PA7 = GRAY_D8/human_ir（不照抄） |
| nrf24l01 | 硬件 SPI1：SCK=PA5/MISO=PA6/MOSI=PA7/CSN(NSS)=PA4 + CE=PA1 + IRQ=PA2(EXTI2) | 全被既有角色占用（不照抄——软 SPI 位操作，无硬件 SPI 外设） |
| rc522 | CS=PA1/SCK=PA2/MOSI=PA3/RST=PA5/MISO=PA4（全 GPIOA 软 SPI） | 全被既有角色占用（不照抄） |
| ir_remote | IR_PIN = PA2，GPIO 外部中断下降沿触发（EXTI2） | PA2 = DEBUG_UART TX（不照抄；改轮询不注册 EXTI） |
| ir_remote_tx | 页面 =「MCU+发射头+接收头、UART 指令」模块：PA8/PA9 附加串口1（USART1）5 字节指令（A1/FA + F1/F2/F3 + 反馈）+9600 | UART 指令解析归生成骨架（ADR 0009），模块只出 NEC GPIO 发射原语（mspm0 定稿同构） |

④ **软 SPI 先例**：max7219/lcd/nrf24l01/rc522 mspm0 = GPIO 位操作忙等，不占硬件 SPI 外设/TIMER；rc522 页面 200us 半周期时序保留（慢但稳）；nrf24l01 mspm0 位操作无延时（NRF 规格 ≤10MHz，72MHz GPIO 翻转达标——stm32 同先例）。

⑤ **红外先例**：ir_remote 页面 = EXTI 下降沿中断同步解码整帧 → 改主循环轮询（stm32 EXTI 聚合/编码器独占先例，ir_beam 轮询先例；忙等 20us 步进，不占 TIMER）；ir_remote_tx 页面 = UART 指令形态 → mspm0 定稿 = 单 GPIO 38kHz NEC 载波（半周期 13.16us；stm32 无 delay_cycles——**delay_us(13)** 忙等翻转，notes 记录精度差异）。

### 各件决策

| 工单 | slug | 类型 | 默认脚（stm32） | API（与 mspm0 对齐） | 说明/notes |
|---|---|---|---|---|---|
| 01 | as32 | A | TX=PB10 / RX=PB11（UART_3，ZIGBEE 互替同脚） | 上表 | **9600**（页面默认 + AS32 出厂默认；`uart_pin_init_ex` 后 `uart_baud_config` 9600 + 关 RXNEIE（轮询——mspm0 同判：避免与 zigbee 同实例名 ISR 重复）；页面接收中断+空闲中断缓冲改轮询排空（SR/DR 直读 + cap 截断修正——页面 `(len+1)%MAX` 回绕覆盖首字节 bug）；AT 配置范围外（页面无 AT 代码——经 as32_send_string 直发或上位机预设，notes） |
| 02 | hc05 | A | TX=PA9 / RX=PA10（UART_1，UWB 互替同脚——mspm0 UART2 同款推理）；STATE=PA8（gpio_in——mspm0 STATE 同脚 PA8 语义：IR_BEAM/WS2812/GRAY_D5）；KEY=PB4（gpio_out——继电器/编码器方向低频） | 上表 | **9600**（HC05 出厂默认；页面代码 115200 与 AT 默认 38400 不一，mspm0 已定 9600——stm32 沿）；RX 中断环形缓冲（`hc05_rx_handler` 进 isr.c 聚合——**pinwriter `_UART_CALLS_ROLES` + 母版 isr.c `__weak` 扩展**）；AT 切换 = KEY 高 + 重上电（HC05 硬件行为，函数仅驱动引脚电平）；页面 STATE=PA7 不照抄 |
| 03 | nrf24l01 | A | CLK=PB10 / MOSI=PB11 / MISO=PB4 / CSN=PB12 / CE=PB13 / IRQ=PB5（**全端口 B，单 `NRF24L01_PORT` 宏**——同口约束照 ttp224 先例；与 ZIGBEE/as32 无线互替、RELAY/编码器方向、DIP/GRAY/TTP/矩阵键盘、编码器/旋钮/称重/粉尘不同框） | 上表 | 软 SPI 位操作（无延时，mspm0 先例）；IRQ 只读状态**不注册 GPIO 中断**（轮询 STATUS——GROUP1/EXTI 独占先例）；`#if DYNAMIC_PACKET==0` 页外符号分支剔除（上游 bug）；页面硬件 SPI1 改软 SPI（F1 页 8 分频 9MHz → 位操作，速度差异 notes）；页面默认脚全不照抄 |
| 04 | rc522 | A | CS=PB0 / RST=PB1 / SCK=PB6 / MOSI=PB4 / MISO=PB5（**全端口 B，单 `RC522_PORT` 宏**；与电机方向/DS18B20、舵机/灰度、继电器/编码器方向、编码器/旋钮/称重/粉尘不同框） | 上表 | 软 SPI 位操作 200us 半周期（页面时序原样）；PcdAuthState UID 复制 6 字节→4 字节修正（上游 bug——越界读 pSnr[4..5]）；CalulateCRC/RC522_Rese 拼写按页面保留；页面默认脚全不照抄 |
| 05 | ir_remote | A | OUT=PA10（gpio_in——mspm0 默认 PA26（UART 族）同型推理：红外遥控与视觉/UWB 链路不同框、同选概率最低；与 ir_remote_tx 默认 PA9 刻意错开——发/收常配对、双选默认不撞） | 上表 | 忙等解码：20us 拍步进（`delay_us`）、引导 9ms+4.5ms、重复码 2.5ms、位低 560us/位高 0=560us/1=1680us、反码校验（页面 `infrared_data_true_judgment` 反码判断逻辑错乱修正——mspm0 同）、**不占 TIMER、不注册 EXTI**（页面 EXTI 下降沿中断改轮询）；单次忙等 ~10ms 等待 + ~50ms 解码 |
| 06 | ir_remote_tx | A | OUT=PA9（gpio_out——mspm0 默认 PA0 同型推理：红外发射与视觉链路不同框、同选概率最低；**与 ir_remote 默认 PA10 刻意错开**） | 上表 | 38kHz 载波 = delay_us(13) 半周期忙等翻转（mspm0 delay_cycles(CPUCLK_FREQ/76000)≈13.16us——stm32 无 delay_cycles，delay_us(13) 误差 ±0.5us，notes）+ 位时序 delay_us（560/1680/2250/4500/9000）；字节内 MSB 先（`IR_TX_MSB_FIRST 1`——与 ir_remote 解码口径一致；标准 NEC LSB 先差异 notes）；页面 UART 指令形态归骨架（notes 给出 5 字节帧提示） |

### 默认脚与重叠全景（定稿）

| slug | 默认脚 | 重叠主体（同选概率最低/互替） |
|---|---|---|
| as32 | TX=PB10 / RX=PB11 | ZIGBEE_UART+key_matrix COL3/4（**无线数传互替件同脚先例**：LoRa 与 Zigbee 二选一接入；同选经绑定换实例/换脚消解——与 open_mv4×digit_uart 同构） |
| hc05 | TX=PA9 / RX=PA10 / STATE=PA8 / KEY=PB4 | DIGIT+COORD+UWB（**无线互替**——mspm0 HC05 与 UWB 同实例同款）+ key_matrix COL1/2、JOYSTICK_SW（PA9/10 同类）+ IR_BEAM/WS2812/GRAY_D5（STATE）+ RELAY/MOTOR_A_ENC_DIR（KEY） |
| nrf24l01 | CLK=PB10 / MOSI=PB11 / MISO=PB4 / CSN=PB12 / CE=PB13 / IRQ=PB5 | ZIGBEE/UART3（无线互替）+ key_matrix COL3/4 + RELAY/ENC_DIR + DIP/GRAY/TTP/KEY_MATRIX（人机输入）+ ENC/EC11/HX711/GP2Y1014（编码器/旋钮/称重/粉尘） |
| rc522 | CS=PB0 / RST=PB1 / SCK=PB6 / MOSI=PB4 / MISO=PB5 | MOTOR_B_DIR+EC11_SW+HX711_DT / MOTOR_B_DIR2+DS18B20 / SERVO+GRAY_D7 / RELAY+ENC_DIR / ENC+EC11_B+HX711_SCK+GP2Y1014（读卡与车类/旋钮/称重/粉尘不同框） |
| ir_remote | OUT=PA10 | DIGIT+COORD+UWB+key_matrix COL2+joystick SW（mspm0 PA26 UART 族同型） |
| ir_remote_tx | OUT=PA9 | DIGIT+COORD+UWB+key_matrix COL1（mspm0 PA0 同型推理；与接收默认 PA10 刻意错开） |

- 白名单登记：PA9/PA10 各 +2（hc05 TX/RX + ir_remote_tx/ir_remote——与既有 UART1 族/键盘/摇杆并列登记）、PB10/PB11 各 +1（as32——ZIGBEE 族/键盘登记组）、PB4 +2（hc05 KEY、nrf MISO）、PB12/PB13 各 +1（nrf CSN/CE——DIP/GRAY/TTP/矩阵组）、PB5 +1（nrf IRQ——ENC/EC11/HX711/GP2Y 组）、PB0/PB1 各 +1（rc522 CS/RST——电机方向/EC11/HX711/DS18B20 组）、PB6 +1（rc522 SCK——SERVO/GRAY_D7 组）。
- **同选消解**：全部同选经引脚绑定换脚（pinwriter 行级覆写）；互替件同脚（as32×zigbee、hc05×uwb、nrf24l01×zigbee/as32、key_matrix×ttp224 等）为「互替同脚先例」语义（二选一接入，无需另消解）；UART 同实例默认共享（hc05×UWB/DIGIT/COORD、as32×ZIGBEE）为「默认共享合法先例」（门禁只查用户绑定，同选时绑定换实例成对消解）。

### 生成侧代码改动（本批首次）

1. `src/contest_generator/pinwriter.py`：`_UART_CALLS_ROLES` 增 `("HC05_UART", "hc05_rx_handler")`（as32 轮询无 handler 不登记——`_UART_CALLS_ROLES` 无 AS32 条目，绑定换实例不影响分组）。
2. 母版 `isr.c`：增 `__weak void hc05_rx_handler(void) {}`。
3. 母版 `pin_config.h`：增宏段（as32 6 宏 / hc05 10 宏 / nrf24l01 7 宏 / rc522 6 宏 / ir_remote 2 宏 / ir_remote_tx 2 宏）+ `USART1_IRQ_CALLS` 增 `hc05_rx_handler()`。
4. `tests/test_pins.py` `STM32_MACRO_VALUES` 补宏；`tests/test_default_layout.py` `WHITELIST` 按上表。

## 测试决策

- 新增 `tests/test_module_as32.py` / `test_module_hc05.py` / `test_module_nrf24l01.py` / `test_module_rc522.py` / `test_module_ir_remote.py` / `test_module_ir_remote_tx.py`（照 test_module_mq2.py 模板：manifest 形状 + 宏存在 + stm32 单选生成全流程 + mspm0 零改动守卫 + 源码守卫）：
  - 形状：stm32 files `[code/<slug>_stm32.c/.h]`、pins（id/type/default/macros）、kit+source_url=地阔星 wiki 原页、notes 关键子串（手册路径/未上板/页面缺陷修正/9600 等）；mspm0 条目原样（零改动守卫 = mspm0 文件仍在 + 生成过门禁）。
  - 守卫（防回潮）：as32 `RX_BUF_MAX 300u` + 轮询（无 IRQHandler）+ cap 截断（无 `% AS32_RX_BUF_MAX` 回绕）；hc05 `HC05_RX_BUF_SIZE 128u` + 9600 + `hc05_rx_handler` 聚合 + 环形缓冲（`% HC05_RX_BUF_SIZE`）；nrf24l01 无延时软 SPI 位操作（`gpio_set/gpio_get` + 无 `SPI1`）+ 无 EXTI 注册；rc522 `delay_us(200)` 半周期 + 4 字节 UID（无 `uc < 6` 复制）+ 无 `PcdAuthState` 越界；ir_remote `IR_TICK_US 20u` + 反码校验（`(uint8_t)~`）+ 无 EXTI/IRQHandler；ir_remote_tx `IR_TX_FREQ_HZ 38000u` + `delay_us(13)` 半周期 + `IR_TX_MSB_FIRST 1` + 无 `TIM_`/`PWM`。
  - 防 banned 模式：printf/main/board_init/GPIO_Init/RCC_/stm32f10x.h/IRQHandler（轮询件）/SPI1（软 SPI 件）。
- `tests/test_pins.py`：`STM32_MACRO_VALUES` 补 ~33 宏（as32 6 + hc05 10 + nrf24l01 7 + rc522 6 + ir_remote 2 + ir_remote_tx 2）+ `USART1_IRQ_CALLS` 更新（含 hc05_rx_handler）。
- `tests/test_default_layout.py`：WHITELIST 按上表登记（注释批次 8 + 互替/同选概率最低语义）。
- 编译矩阵：UV4 0/0（MAIN_C 调全部 API，(void) 化——as32 带 receive/flush、hc05 带 available/receive/is_connected/at_mode、nrf24l01 带 tx/rx_packet、rc522 带 read_card/auth/read/write/halt、ir_remote 带 poll/get/clear、ir_remote_tx 带 send/send_repeat）。
- 词表：六件零补录（已挂接 mspm0 批——复核 lib_modules 命中）。

## 范围外

- mspm0 条目改动（A 类零改动）；B 类新模块；上板真机验证（蓝药丸红外管/载波、LoRa 透传、RC522 软 SPI 时序、HC05 9600 对码——notes 注明）。
- nrf24l01 接收的 EXTI 中断方式（页面「中断方式接收」——本件轮询，GROUP1/EXTI 独占先例；notes 说明可扩展）。
- ir_remote_tx 页面 UART 指令协议（A1/FA + F1/F2/F3 + 反馈）解析（归生成骨架——notes 给出提示）。
- as32 AT 配置指令（MD0/MD1 模式脚未接线——页面无 AT 代码；经 as32_send_string 配置模式直发或上位机预设，notes）。
- 软 SPI 时序真机标定（rc522 200us 半周期/nrf24l01 无延时——真机异常时调/补 delay，notes 给唯一时序宏点）。

## 补充说明

- 排序：01 as32 → 02 hc05（UART 仲裁两件先打样聚合面）→ 03 nrf24l01 → 04 rc522（软 SPI 两件）→ 05 ir_remote → 06 ir_remote_tx（红外收发配对对仗）。
- 页内事实 = 地阔星 F1 页（`sources/materials/lckfb-地阔星移植手册/rf--*.md`）+ mspm0 侧 batch-facts（`%TEMP%` batch1/3/4-facts.md）+ 库内 mspm0 源码（API 现名唯一事实源）。
- 收尾清单：全量测试 → sweep 更新（`sweep_6_modules.py`）→ code-review 两轴 → CONTEXT 补录 → 中文提交。
