# 06 — ir_remote_tx 红外编码发射（38kHz NEC 载波，手册 rf--Infrared-decoding-coding-module.md）

**要做什么：** 模块库 `ir_remote_tx` 新增 **stm32 平台条目**（mspm0 零改动）：API 与 mspm0 完全对齐（ir_tx_init / ir_tx_send(address, command) / ir_tx_send_repeat；IR_TX_FREQ_HZ 38000u、IR_TX_MSB_FIRST 1）。单 GPIO 直出 38kHz NEC 载波：半周期 **delay_us(13)**（13.16us——mspm0 delay_cycles(CPUCLK_FREQ/76000) 先例；stm32 无 delay_cycles，delay_us(13) 误差 ±0.5us、载波 ~37.8-38.5kHz，notes）+ 位时序 delay_us（560/1680/2250/4500/9000）；**不占 TIMER/PWM**；页面「MCU+发射头+接收头、UART 指令」形态（PA8/PA9 串口1 5 字节帧 A1/FA + F1/F2/F3 + 反馈）**解析归生成骨架**（ADR 0009——notes 给骨架提示），模块只出 NEC 发射原语。

**关键事实（F1 页 + mspm0 定稿）：** 页面 = UART 指令形态（USART1 PA8/PA9、9600）——不照抄（模块为 GPIO 载波原语）。**默认 OUT=PA9**（gpio_out——mspm0 默认 PA0 同型推理：红外发射与视觉/数传链路不同框、同选概率最低；**与 ir_remote 默认 PA10 刻意错开**——发/收常配对、双选默认不撞；发射管串 100-200Ω 限流、5V 供电 notes）。

**引脚：** `IR_TX_OUT`（gpio_out，PA9，macros `[IR_TX_PORT, IR_TX_OUT_PIN]`）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论回填（2026-09-07）：全部完成。stm32 条目 = 38kHz NEC 载波发射件：API 与 mspm0 全对齐（ir_tx_init/ir_tx_send(address, command)/ir_tx_send_repeat + IR_TX_FREQ_HZ 38000u + IR_TX_MSB_FIRST 1——ir_remote_tx.h 现名逐字对齐）。默认 **OUT=PA9**（gpio_out——mspm0 默认 PA0 同型推理：红外发射与视觉/数传链路不同框、同选概率最低；**与 ir_remote 接收默认 PA10 刻意错开**——发/收常配对、双选默认不撞）；F1 页 = UART 指令形态（PA8/PA9 串口1 5 字节帧 A1/FA + F1/F2/F3 + 反馈 9600）**解析归生成骨架**（notes 给 F1=发射/F2 改地址/F3 改波特率语义提示）。**载波 = delay_us(13) 半周期忙等翻转**（mspm0 delay_cycles(CPUCLK_FREQ/76000)≈13.16us 先例；stm32 无 delay_cycles——delay_us(13) 误差 ±0.5us（载波 ~37.8-38.5kHz、ir_remote 20us 拍阈值全在脉宽中央、配对无碍）notes）；**周期数公式 `us×38000/1e6`**（mspm0 code-review 修正防回潮：早产「us/2 轮」放大 13.16×）；位时序 delay_us（560/1680/2250/4500/9000）；**不占 TIMER/PWM**、不注册中断；单帧阻塞 ~50-90ms（notes 提醒调用方节拍）；MSB 先（标准 NEC LSB 先差异——控市售设备改宏=0）。**F1 换算**：GPIO_Init/WriteBit → ml_gpio（gpio_init/gpio_set），页面 USART 部分不落模块，零引脚字面量。verified=true（UV4 0 error/0 module warning，2026-09-07，6bd0acc3）+ kit/source_url + notes（手册/原页/网盘/页面 UART 形态归骨架/PA9 推理+与接收 PA10 错开/delay_us(13) 精度/MSB 先差异/限流电阻/未上板）；wordlist 零补录；mspm0 零改动；description 双平台化；test_pins 宏表 +2 宏、test_default_layout PA9 白名单 +ir_remote_tx。

**实施清单：**
- [ ] `library/modules/ir_remote_tx/code/ir_remote_tx_stm32.c/.h`（mspm0 实现换算：DL_GPIO_setPins/clearPins → gpio_set；`ir_tx_burst` delay_us(13) 半周期翻转（周期数 = us×38000/1e6——mspm0 code-review 修正公式防回潮）；ir_tx_send 4 字节 MSB 先；重复码）
- [ ] manifest.json platforms 增 stm32（files、dependencies ["delay"]、verified false、hardware_bound false、pins 1 行、kit/source_url 地阔星原页、notes：手册/原页/网盘/页面 UART 形态归骨架 + 5 字节帧提示/默认 PA9 推理 + 与接收 PA10 错开/delay_us(13) 精度记录/字节内 MSB 先 + 标准 NEC LSB 差异（控市售设备改宏=0）/限流电阻/未上板）
- [ ] pin_config.h 增 IR_TX 宏段（2 宏）
- [ ] 测试 `tests/test_module_ir_remote_tx.py`（形状+宏存在+单选生成+mspm0 零改动+守卫：`IR_TX_FREQ_HZ 38000u`、`delay_us(13)`（半周期）、`IR_TX_MSB_FIRST 1`、`IR_TX_REPEAT_HIGH_US 2250u`、无 `TIM_`/`PWM`/`USART`）
- [ ] test_pins.py 补 2 宏；test_default_layout.py PA9 登记
- [ ] UV4 矩阵 0/0 → verified=true
- [ ] wordlist 零补录复核；中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0；mspm0 零改动。
