# 03 — nrf24l01 2.4G 无线收发（软 SPI 六脚位操作，手册 rf--nrf24l01-2-4-g-control-module.md）

**要做什么：** 模块库 `nrf24l01` 新增 **stm32 平台条目**（mspm0 零改动）：API 与 mspm0 完全对齐（nrf24l01_init / set_channel / set_speed / set_power / set_address / set_mode / tx_packet / rx_packet / flush_rx / flush_tx + 枚举/返回码常量，全照 mspm0 头名）。软 SPI 位操作六脚（CLK/MOSI/CSN/CE 输出 + MISO/IRQ 输入）——**不占硬件 SPI 外设/TIMER**（页面硬件 SPI1 8 分频 9MHz → 位操作；mspm0 先例无延时——72MHz GPIO 翻转达标 ≤10MHz，notes）；IRQ 只读状态**不注册 GPIO 中断**（轮询 STATUS——EXTI 聚合/编码器独占先例）；`#if DYNAMIC_PACKET==0` 页外符号分支剔除（上游 bug，mspm0 同）。

**关键事实（F1 页）：** 页面默认 = 硬件 SPI1（SCK=PA5/MISO=PA6/MOSI=PA7/NSS=PA4）+ CE=PA1 + IRQ=PA2(EXTI2)——全被既有角色占用不照抄。**默认脚 = 全端口 B**（单 `NRF24L01_PORT` 宏，同口约束照 ttp224 先例）：CLK=PB10 / MOSI=PB11（ZIGBEE_UART+key_matrix COL3/4——**无线数传互替件同脚**）、MISO=PB4（RELAY+编码器方向）、CSN=PB12 / CE=PB13（DIP+GRAY+TTP224+KEY_MATRIX 人机输入组）、IRQ=PB5（编码器/EC11/称重/粉尘）。

**引脚：** 6 行（id 照 mspm0：NRF24L01_CLK/MOSI/MISO/CSN/CE/IRQ；type gpio_out/gpio_out/gpio_in/gpio_out/gpio_out/gpio_in；每行 macros 含共享 `NRF24L01_PORT` + 各自 `_PIN`）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论回填（2026-09-07）：全部完成。stm32 条目 = 软 SPI 六脚位操作件：API 与 mspm0 全对齐（nrf24l01_init/set_channel/set_speed/set_power/set_address/set_mode/tx_packet/rx_packet/flush_rx/flush_tx + 枚举/返回码/PAYLOAD_MAX 32——nrf24l01.h 现名逐字对齐）。默认 = **全端口 B 单 `NRF24L01_PORT=GPIO_B` 宏**（同口约束照 ttp224——6 角色每行都挂共享 PORT 宏，pinwriter `_check_shared_port_macro_conflicts` 拦异值）：CLK=PB10/MOSI=PB11（ZIGBEE+as32+key_matrix COL3/4——无线数传互替件同脚先例）、MISO=PB4（RELAY+编码器方向+hc05 KEY）、CSN=PB12/CE=PB13（DIP+GRAY+TTP224+KEY_MATRIX 人机输入组）、IRQ=PB5（编码器/EC11/HX711/GP2Y1014 组）；F1 页硬件 SPI1 五脚（PA5/6/7/4）+CE=PA1+IRQ=PA2(EXTI2) 全不照抄。**位操作零延时**（mspm0 先例；72MHz GPIO 翻转规格内——notes 给真机异常唯一时序宏点）；IRQ 只读不注册 EXTI（轮询 STATUS——EXTI 聚合/编码器独占先例）；DYNAMIC_PACKET==0 页外符号（L01_WriteSingleReg）剔除、FLUSH 显式命令、`_write_buf` OR 写位（mspm0 code-review 修正同款）、TxPacket 500ms 超时返回 TX_ERR。**F1 换算**：GPIO_Init/WriteBit/ReadInputDataBit → ml_gpio（gpio_init/gpio_set/gpio_get），零引脚字面量。verified=true（UV4 0 error/0 module warning，2026-09-07，573a2629）+ kit/source_url + notes（手册/原页/网盘/软 SPI 换算+速度差异/默认脚推理/互替件同脚/上游 bug/未上板）；wordlist 零补录；mspm0 零改动；description 双平台化；test_pins 宏表 +7 宏、test_default_layout PB10/PB11/PB4/PB12/PB13/PB5 白名单 +nrf（分组断言同步）。

**实施清单：**
- [ ] `library/modules/nrf24l01/code/nrf24l01_stm32.c/.h`（mspm0 实现逐函数换算：DL_GPIO_* → gpio_init/gpio_set/gpio_get；零延时位操作 `_spi_read_write_byte`；全套寄存器原语静态化；seed 地址 0x34,0x43,0x10,0x10,0x01）
- [ ] manifest.json platforms 增 stm32（files、dependencies ["delay"]、verified false、hardware_bound false、pins 6 行、kit/source_url 地阔星原页、notes：手册/原页/网盘/硬件 SPI1→软 SPI 换算+速度差异/页面默认脚弃用+全 B 口推理/互替件同脚/无 EXTI 轮询/DYNAMIC_PACKET 上游 bug 剔除/未上板）
- [ ] pin_config.h 增 NRF24L01 宏段（7 宏：PORT + 6 × PIN）
- [ ] 测试 `tests/test_module_nrf24l01.py`（形状+宏存在+单选生成+mspm0 零改动+守卫：无 `SPI1`/无 `SPI_I2S`/无 `EXTI`/无 `IRQHandler`、gpio_set/gpio_get 位操作、`NRF24L01_PORT` 共享宏、返回值常量钉值）
- [ ] test_pins.py 补 7 宏；test_default_layout.py PB10/PB11/PB4/PB12/PB13/PB5 登记
- [ ] UV4 矩阵 0/0 → verified=true
- [ ] wordlist 零补录复核；中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0；mspm0 零改动。
