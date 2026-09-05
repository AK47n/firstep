# 01 — flame 模块（火焰传感器，手册 sensor--flame-sensor.md）

**要做什么：** 模块库新增 `flame` 条目（仅 mspm0）：从手册提炼火焰驱动为纯驱动切片——ADC 模拟量读 AO 出 0-100% 火焰强度百分比。**ADC 独立 MEM6（照 mq135/mq5 模式）**：ADC12_0 sequence 开 MEM6（endAdd 5→6、adcMem6chansel=CHAN_7、adcPin7=PA22——MEM 倒数第二槽；剩余 A0 通道按冲突矩阵定稿：PA27/PA26/PA25 已归 MEM1-3、PB20/PB24 已归 MEM4/5，剩下 PA22（A0_7，干净通道）与 PA14（A0_12，板载 LED2+15k 负载会分流高阻光电二极管源）——火焰 AO 为高阻电流源，取 PA22）。`flame_init()` + `flame_read_percent()`（页面原式**反向映射**（1 − value/4095）×100——红外光越强 ADC 值越小、百分比越高，页面 4095/100 原式、5 次快平均照 mq2）；页面 ADC 中断改轮询（照 mq2/ir_distance）；页面 DO（LM393 阈值）宏未用不声明；notes 写明 700-1000nm 探测/换向换算/相对强度非绝对值。

**被谁阻塞：** 无——可立即开始（adc 模块 API 扩展在本工单内顺带完成）。

**状态：** claimed

- [ ] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--flame-sensor.md` 「代码块」章节抽完整 `bsp_flame.c/h` → 改造为 `code/flame.c` + `code/flame.h`：去 main/printf、函数名规范化（`flame_init/flame_read_percent`，去 `ADC_FLAME_Init/ADC_GET/Get_Adc_FLAME_Value/Get_FLAME_Percentage_value` 命名）、ADC 中断（IRQHandler + gCheckADC）改经 adc 模块 API 轮询（无 IRQHandler 强符号）、`GET_DO`/`Get_FLAME_Do_value` 不声明（mq2 同策略，notes）
- [ ] adc 模块扩展：`adc_mspm0.h/.c` 的 `adc_get` 通道守卫 `> ADC_Channel_5` → `> ADC_Channel_6`，枚举注释/数据所有权注释同步（MEM6=MEM7 归 flame/soil——MEM6 归 flame + 预留说明）；`tests/test_pins.py` 豁免元组增 `"flame"`
- [ ] 母版 `mspm0.syscfg`：ADC12_0 sequence 加第 7 通道——`endAdd 5→6`、`adcMem6chansel="DL_ADC12_INPUT_CHAN_7"`、`adcPin7.$assign="PA22"`；ADC 段注释同步（六通道 → 七通道、MEM6 归 flame、剩余槽 MEM7 预留 soil）
- [ ] `syscfg_instances.py` INSTANCE_CONSUMERS：`ADC12_0` 元组增 `"flame"`（soil 随 02 工单加入）
- [ ] `manifest.json`：`dependencies: ["adc"]`；mspm0 平台条目（files/verified false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接（资料 risv/案例 1x05）+改造要点+**反向映射与 700-1000nm 说明**+**MEM 槽位剩余说明**+编译记录）；pins：`FLAME_AO_CH6` = adc 默认 PA22（尾 `_CH<N>` 推导 MEM 索引）；简介判据：能力方向（火源探测/灭火机器人/火警报警联动）+ 无题绑定
- [ ] wordlist.json 补录：「感知传感器」加「火焰传感器（红外）」方案挂 `lib_modules: ["flame"]`，models 加 "火焰传感器"
- [ ] 测试：`tests/test_pin_bindings.py` 刻意表更新（PA22 4→5 注释补 flame）；`tests/test_syscfg_prune.py` ADC12_0 新消费方（flame）断言；新增 `tests/test_module_flame.py`（manifest 结构 + 单选生成 + 公式守卫（4095/100.0f + `1.0f -` 反向 + ADC_Channel_6）+ 无 IRQHandler 守卫 + notes 守卫）；**旧断言同步**：test_module_ir_distance.py（endAdd 5→6）、test_module_mq135.py（endAdd 5→6 + `> ADC_Channel_5`→`> ADC_Channel_6`）、test_module_mq5.py（endAdd）、test_module_joystick.py（注释 六通道→七通道）
- [ ] 编译验证：`run_flame_matrix.py` 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录；code-review 后中文提交
