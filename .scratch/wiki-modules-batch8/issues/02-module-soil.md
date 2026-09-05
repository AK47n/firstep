# 02 — soil 模块（土壤湿度传感器，手册 sensor--soil-moisture-sensor.md）

**要做什么：** 模块库新增 `soil` 条目（仅 mspm0）：从手册提炼土壤湿度驱动为纯驱动切片——ADC 模拟量读 AO 出 0-100% 相对湿度。**ADC 独立 MEM7（最后一个槽！）**：ADC12_0 sequence 开 MEM7（endAdd 6→7、adcMem7chansel=CHAN_12、adcPin12=PA14——剩余 A0 通道仅 PA14；板载 LED2+15k 负载为固定比率衰减：读数系统性偏小但单调性保留（相对湿度判定/阈值可用），notes 写明限制）。`soil_init()` + `soil_read_percent()`（页面原式正向 `value/4095×100`——区别于 flame 反向映射；5 次快平均照 mq2）；页面 ADC 中断改轮询；页面 DO（LM393 阈值）宏未用不声明；**完成后把「MEM 槽位已满（8/8）」写进 spec 与 CONTEXT——后续 ADC 类（photoresistance/rain/gp2y1014au/s12sd/ms1100）一律薄封装共读 MEM0 模式（mq2/us016 先例，notes 写明多器件共读限制）**。

**被谁阻塞：** 01 flame（同一 ADC12_0 sequence 演进，endAdd 5→6 在前——串行）。

**状态：** resolved

**结论：** 2026-09-06 完成并提交（0fbe841d）。土壤湿度 ADC 模拟量独立 MEM7 通道（**最后一个 MEM 槽位——槽位已满（8/8）**：后续 ADC 类件（photoresistance/rain/gp2y1014au/s12sd/ms1100）一律薄封装共读 MEM0 模式（mq2/us016 先例——多件同选同读一物理通道、一次转换一次读、采样节奏按用途自协调，notes 写明限制））；母版 syscfg ADC12_0 sequence 加第 8 通道（endAdd 6→7、adcMem7chansel=CHAN_12、adcPin12=PA14——剩余通道仅 PA14（板载 LED2+15k 固定比率衰减：读数系统偏小、单调性保留）；与 DCC_100_PWM2/WS2812 IN/RC522 SCK/AGS10 SDA 重叠——同选概率最低）；`soil_init` + `soil_read_percent` 出 0-100% 土壤湿度（页面原式**正向映射** value/4095×100——水分越足 ADC 值越大、百分比越高，区别于 flame 反向；30 次→5 次快平均；页面注释「Get_Adc_Dma_Value」系函数名残留正常收敛）；页面 ADC 中断改经 adc 模块 API 轮询；adc 模块 adc_get 通道守卫扩展至 MEM7；页面 DO（LM393 阈值）宏未用不声明；默认 PA14；词表感知传感器 +土壤湿度传感器；单选生成 → SysConfig CLI → gmake 0 error/0 warning（verified=true）；旧断言全量同步（endAdd 6→7：flame/ir_distance/mq135/mq5/joystick）；「MEM 槽位已满（8/8）」已写入 spec 与 CONTEXT 平台行。

- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--soil-moisture-sensor.md` 「代码块」章节抽完整 `bsp_soilHumidity.c/h` → 改造为 `code/soil.c` + `code/soil.h`：去 main/printf、函数名规范化（`soil_init/soil_read_percent`）、ADC 中断改经 adc 模块 API 轮询、`GET_DO`/`Get_SH_DO_value` 不声明（mq2 同策略，notes）
- [x] adc 模块扩展：`adc_get` 通道守卫 `> ADC_Channel_6` → `> ADC_Channel_7`，枚举注释/数据所有权注释同步（MEM7 归 soil）；`tests/test_pins.py` 豁免元组增 `"soil"`
- [x] 母版 `mspm0.syscfg`：ADC12_0 sequence 加第 8 通道——`endAdd 6→7`、`adcMem7chansel="DL_ADC12_INPUT_CHAN_12"`、`adcPin12.$assign="PA14"`；ADC 段注释同步（八通道、MEM7 归 soil、**MEM 槽位已满 8/8**）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS：`ADC12_0` 元组增 `"soil"`
- [x] `manifest.json`：`dependencies: ["adc"]`；mspm0 平台条目（files/verified true/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接（资料 8889/案例 5mtq）+改造要点+**15k 负载限制（固定比率衰减、单调性保留）**+**正面换算说明**+**薄封装共读 MEM0 模式决策（槽位已满 8/8）**+编译记录）；pins：`SOIL_AO_CH7` = adc 默认 PA14；简介判据：能力方向（土壤湿度检测/自动浇花/智慧农业/湿度报警联动）+ 无题绑定
- [x] wordlist.json 补录：「感知传感器」加「土壤湿度传感器」方案挂 `lib_modules: ["soil"]`，models 加 "土壤湿度传感器"
- [x] 测试：`tests/test_pin_bindings.py` 刻意表更新（PA14 4→5 注释补 soil）；`tests/test_syscfg_prune.py` ADC12_0 新消费方（soil）断言；新增 `tests/test_module_soil.py`（manifest 结构 + 单选生成 + 公式守卫（4095/100.0f + 正向无 `1.0f -` + ADC_Channel_7）+ 无 IRQHandler 守卫 + notes 守卫（含 15k/MEM0 共读决策））；**旧断言全量同步**：test_module_ir_distance.py、test_module_mq135.py（endAdd 6→7 + `> ADC_Channel_7`）、test_module_mq5.py（endAdd）、test_module_joystick.py（注释 七通道→八通道）、test_module_flame.py（endAdd 6→7）
- [x] 编译验证：`run_soil_matrix.py` 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录；code-review 后中文提交；spec/CONTEXT 补「MEM 槽位已满（8/8）」决策
