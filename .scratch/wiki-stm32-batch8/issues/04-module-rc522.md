# 04 — rc522 射频 IC 卡读卡（软 SPI 五脚位操作，手册 rf--rc522-rf-ic-card-identification-module.md）

**要做什么：** 模块库 `rc522` 新增 **stm32 平台条目**（mspm0 零改动）：API 与 mspm0 完全对齐（rc522_init / rc522_read_card(uid[4]) / rc522_auth_block / rc522_read_block / rc522_write_block / rc522_halt + RC522_OK/NOTAGERR/ERR/AUTH_KEYA/KEYB 常量）。软 SPI 位操作五脚（CS/RST/SCK/MOSI 输出 + MISO 输入）——**不占硬件 SPI 外设/TIMER**；页面 200us 半周期时序保留（慢但稳）；PcdAuthState UID 复制 **6 字节→4 字节修正**（页面越界读 pSnr[4..5] 上游 bug——mspm0 同）；CalulateCRC/RC522_Rese 拼写按页面保留。

**关键事实（F1 页）：** 页面默认 = CS=PA1/SCK=PA2/MOSI=PA3/RST=PA5/MISO=PA4（全 GPIOA）——全被既有角色占用不照抄。**默认脚 = 全端口 B**（单 `RC522_PORT` 宏，同口约束照 ttp224 先例）：CS=PB0 / RST=PB1 / SCK=PB6 / MOSI=PB4 / MISO=PB5——读卡与车类（电机方向/舵机）、旋钮（EC11）、称重（HX711）、粉尘（GP2Y1014）、DS18B20、编码器不同框、同选概率最低。

**引脚：** 5 行（id 照 mspm0：RC522_CS/RST/SCK/MOSI/MISO；type gpio_out×4 + gpio_in；每行 macros 含共享 `RC522_PORT` + 各自 `_PIN`）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论回填（2026-09-07）：全部完成。stm32 条目 = 软 SPI 五脚位操作件：API 与 mspm0 全对齐（rc522_init/read_card(uid[4])/auth_block/read_block/write_block/halt + RC522_OK/NOTAGERR/ERR + AUTH_KEYA/KEYB——rc522.h 现名逐字对齐；Pcd* 通信族全套驱动内静态）。默认 = **全端口 B 单 `RC522_PORT=GPIO_B` 宏**（同口约束照 ttp224/nrf24l01）：CS=PB0（MOTOR_B_DIR+HX711_DT+EC11_SW）/RST=PB1（MOTOR_B_DIR2+DS18B20）/SCK=PB6（SERVO+GRAY_D7）/MOSI=PB4（RELAY+编码器方向+hc05 KEY+nrf MISO）/MISO=PB5（编码器+EC11_B+HX711_SCK+GP2Y1014+nrf IRQ）——读卡与车类/旋钮/称重/粉尘不同框、同选概率最低；F1 页默认（CS=PA1/SCK=PA2/MOSI=PA3/RST=PA5/MISO=PA4）全不照抄。**200us 半周期页面时序保留** + **UID 复制 4 字节修正**（页面 6 字节越界 bug——mspm0 同）+ CalulateCRC/RC522_Rese 拼写保留；**`_antenna_off` 未引用裁剪**（UV4 首轮 #177-D 未引用告警——mspm0 版保留原函数、stm32 版裁剪未引用静态，语义等价，notes 记录）。**F1 换算**：GPIO API → ml_gpio + delay_us 同名，零引脚字面量；gpio_init 在 rc522_init 完成（页面 GPIO_Init 换算）。verified=true（UV4 0 error/0 module warning，2026-09-07，f9979a10）+ kit/source_url + notes（手册/原页/网盘/200us 时序+真机标定/默认脚推理/UID 修正/拼写保留/未上板）；wordlist 零补录；mspm0 零改动；description 双平台化；test_pins 宏表 +6 宏、test_default_layout PB0/PB1/PB6/PB4/PB5 白名单 +rc522（分组断言同步）。

**实施清单：**
- [ ] `library/modules/rc522/code/rc522_stm32.c/.h`（mspm0 实现逐函数换算：DL_GPIO_* → gpio_init/gpio_set/gpio_get、delay_us(200) 半周期；寄存器操作族/基础通信/ISO14443 通信族全套静态化 + 对外服务函数；`_auth_state` UID 4 字节）
- [ ] manifest.json platforms 增 stm32（files、dependencies ["delay"]、verified false、hardware_bound false、pins 5 行、kit/source_url 地阔星原页、notes：手册/原页/网盘/页面默认脚弃用+全 B 口推理/200us 时序+真机标定/UID 4 字节修正/拼写保留/未上板）
- [ ] pin_config.h 增 RC522 宏段（6 宏：PORT + 5 × PIN）
- [ ] 测试 `tests/test_module_rc522.py`（形状+宏存在+单选生成+mspm0 零改动+守卫：`delay_us(200)`、`RC522_PORT` 共享宏、`for (uc = 0; uc < 4; uc++)` UID 复制（无 `uc < 6` 越界）、无 `SPI1`、返回码钉值）
- [ ] test_pins.py 补 6 宏；test_default_layout.py PB0/PB1/PB6/PB4/PB5 登记
- [ ] UV4 矩阵 0/0 → verified=true
- [ ] wordlist 零补录复核；中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0；mspm0 零改动。
