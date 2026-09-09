# 05 — ir_remote 红外遥控接收解码（GPIO 轮询忙等，手册 rf--infrared-receiving-module.md）

**要做什么：** 模块库 `ir_remote` 新增 **stm32 平台条目**（mspm0 零改动）：API 与 mspm0 完全对齐（ir_remote_init / ir_remote_poll（1=新帧/2=重复码/0=超时无效）/ ir_remote_get_address / ir_remote_get_code / ir_remote_has_data / ir_remote_clear）。**忙等解码**：20us 拍步进（`delay_us(20)`）测量脉宽——引导码 9ms+4.5ms、重复码 9ms+2.5ms、位低 560us/位高 0=560us/1=1680us、反码校验（`~a==a' && ~c==c'`）——**不占 TIMER、不注册 EXTI**（页面 EXTI2 下降沿中断同步解码整帧改主循环轮询——ir_beam 轮询先例、EXTI 聚合/编码器独占；mspm0 同判）；页面 `infrared_data_true_judgment` 反码判断逻辑错乱已修正。

**关键事实（F1 页）：** 页面默认 IR_PIN=PA2（GPIO_EXTI 下降沿）——DEBUG_UART TX 常备件不照抄。**默认 OUT=PA10**（gpio_in——mspm0 默认 PA26（UART 族）同型推理：红外遥控与视觉/UWB 链路不同框、同选概率最低；与 ir_remote_tx 默认 PA9 刻意错开——发/收常配对、双选默认不撞）。

**引脚：** `IR_REMOTE_OUT`（gpio_in，PA10，macros `[IR_REMOTE_PORT, IR_REMOTE_OUT_PIN]`）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论回填（2026-09-07）：全部完成。stm32 条目 = 轮询忙等解码件：API 与 mspm0 全对齐（ir_remote_init/poll（1=新帧/2=重复码/0=超时无效）/get_address/get_code/has_data/clear——ir_remote.h 现名逐字对齐）。默认 **OUT=PA10**（gpio_in 上拉——mspm0 默认 PA26（UART 族）同型推理：红外遥控与视觉/UWB 链路不同框、同选概率最低；与 ir_remote_tx 默认 PA9 **刻意错开**——发/收常配对、双选默认不撞）；F1 页默认 PA2/EXTI2 不照抄（DEBUG_UART TX 常备件）。**EXTI 改轮询**（页面 EXTI2 下降沿中断同步解码 → 主循环 20us 拍忙等——EXTI 聚合/编码器独占先例（ir_beam 轮询先例）；**不注册 EXTI、不占 TIMER**——`_check_exti_line_conflicts` 默认组合不拦（本件轮询无 handler））；20us 拍阈值与 mspm0 逐字一致；**反码严格校验**（页面 `infrared_data_true_judgment` 错乱——命令反码不等返回 1 仍落库——修正，mspm0 同）；位判定两窗口皆不中 → 整帧失败（更严，mspm0 同）；位序 MSB 先（与 ir_remote_tx 发射配对）。**F1 换算**：GPIO_Init/ReadInputDataBit/EXTI_* → ml_gpio（gpio_init/gpio_get），零引脚字面量。verified=true（UV4 0 error/0 module warning，2026-09-07，e22f5e68）+ kit/source_url + notes（手册/原页/网盘/PA10 推理+与 TX PA9 错开/EXTI 改轮询/反码修正/20us 拍/未上板）；wordlist 零补录；mspm0 零改动；description 双平台化；test_pins 宏表 +2 宏、test_default_layout PA10 白名单 +ir_remote。

**实施清单：**
- [x] `library/modules/ir_remote/code/ir_remote_stm32.c/.h`（mspm0 实现换算：DL_GPIO_readPins → gpio_get、delay_us(20)；`_measure` 忙等 + 阈值 400-500/100-250/100-150/20-60/60-100/10-50 拍；反码校验）
- [x] manifest.json platforms 增 stm32（files、dependencies ["delay"]、verified false、hardware_bound false、pins 1 行、kit/source_url 地阔星原页、notes：手册/原页/网盘/页面默认 PA2 弃用 + PA10 推理 + 与 TX PA9 错开/EXTI 改轮询/反码判断修正/20us 拍忙等不占 TIMER/未上板）
- [x] pin_config.h 增 IR_REMOTE 宏段（2 宏）
- [x] 测试 `tests/test_module_ir_remote.py`（形状+宏存在+单选生成+mspm0 零改动+守卫：`IR_TICK_US 20u`、`delay_us(20)`、`(uint8_t)~value` 反码校验、无 `EXTI`/`IRQHandler`/`TIM_`）
- [x] test_pins.py 补 2 宏；test_default_layout.py PA10 登记
- [x] UV4 矩阵 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0；mspm0 零改动。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
