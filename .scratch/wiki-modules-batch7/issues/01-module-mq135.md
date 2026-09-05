# 01 — mq135 模块（MQ-135 空气质量传感器，手册 sensor--mq-135-sensor.md）

**要做什么：** 模块库新增 `mq135` 条目（仅 mspm0）：从手册提炼 MQ-135 驱动为纯驱动切片——ADC 模拟量读 AO 出 0-100% 相对浓度。**独立 MEM 通道（ir_distance 先例）而非 mq2 的 MEM0 薄封装**：ADC12_0 sequence 开 MEM4（endAdd 3→4、adcMem4chansel=CHAN_6、adcPin6=PB20）——多路气体同选时各器件物理通道独立、无共读冲突（mq2 薄封装共读 adc 模块 MEM0，与 mq135 同选会撞同一物理通道）。`mq135_init()` + `mq135_read_percent()`（4095/100 页面原式、5 次快平均照 mq2）；页面 ADC 中断改轮询（照 mq2/ir_distance）；notes 写明与 mq2 的通道方案差异与 MQ 系"相对值非 ppm 精标 + 预热"限制。

**被谁阻塞：** 无——可立即开始（adc 模块 API 扩展在本工单内顺带完成）。

**状态：** resolved

**结论：** 2026-09-08 完成并提交（4575146c）。ADC 模拟量独立 MEM4 通道（ir_distance 先例而非 mq2 的 MEM0 薄封装——多路气体同选时各器件物理通道独立、无共读冲突）；母版 syscfg ADC12_0 sequence 加第 5 通道（endAdd 3→4、adcMem4chansel=CHAN_6、adcPin6=PB20——地猛星板上 ADC0 剩余通道中同选概率最低：与 DC_MOTOR BB/SYN6288 TX 重叠）；`mq135_init` + `mq135_read_percent` 出 0-100% 相对浓度（页面 4095/100 原式、30 次→5 次快平均）；页面 ADC 中断（IRQHandler + gCheckADC）改经 adc 模块 API 轮询（共享实例强符号唯一）；adc 模块 adc_get 通道守卫扩展至 MEM5（枚举/注释同步）；页面 DO（LM393 阈值）宏未用不声明；notes 写明与 mq2 的通道方案差异与 MQ 系相对值非 ppm 精标+预热限制；词表感知传感器 +MQ-135；单选生成 → SysConfig CLI → gmake 0 error/0 warning（verified=true）；code-review 双轴通过（收尾修正见 136b982d）。

- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--mq-135-sensor.md` 「代码块」章节抽完整 `bsp_mq135.c/h` → 改造为 `code/mq135.c` + `code/mq135.h`：去 main/printf、函数名规范化（`mq135_init/mq135_read_percent`，去 `ADC_MQ135_Init/Get_Adc_MQ135_Value/Get_MQ135_Percentage_value` 命名）、ADC 中断（IRQHandler + gCheckADC）改经 adc 模块 API 轮询（无 IRQHandler 强符号）、`MQ_DO`/`Get_MQ135_DO_value` 不声明（mq2 同策略，notes）
- [x] adc 模块扩展：`adc_mspm0.h/.c` 的 `adc_get` 通道守卫 `> ADC_Channel_3` → `> ADC_Channel_5`，枚举注释/数据所有权注释同步（MEM4=MEM5 归 mq135/mq5）；`tests/test_pins.py` 豁免元组增 `"mq135"`/`"mq5"`
- [x] 母版 `mspm0.syscfg`：ADC12_0 sequence 加第 5 通道——`endAdd 3→4`、`adcMem4chansel="DL_ADC12_INPUT_CHAN_6"`、`adcPin6.$assign="PB20"`；ADC 段注释同步（四通道 → 五通道、MEM4 归 mq135）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS：`ADC12_0` 元组增 `"mq135"`（mq5 随 02 工单加入）
- [x] `manifest.json`：`dependencies: ["adc"]`；mspm0 平台条目（files/verified true/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接（资料 9966/案例 quhb）+改造要点+**与 mq2 通道方案差异**+**MQ 系相对值非 ppm 精标+预热**+编译记录）；pins：`MQ135_AO_CH4` = adc 默认 PB20（尾 `_CH<N>` 推导 MEM 索引）；简介判据：能力方向（气体检测/空气质量监测/浓度报警）+ 无题绑定
- [x] wordlist.json 补录：「感知传感器」加「MQ-135 空气质量传感器」方案挂 `lib_modules: ["mq135"]`，models 加 "MQ-135"
- [x] 测试：`tests/test_pin_bindings.py` 刻意表更新（PB20 2→3 注释补 mq135）；`tests/test_syscfg_prune.py` ADC12_0 新消费方（mq135）断言；新增 `tests/test_module_mq135.py`（manifest 结构 + 单选生成 + 百分比公式守卫 + 无 IRQHandler 守卫 + notes 守卫）；**旧断言同步**：test_module_ir_distance.py（endAdd 3→4）、test_module_joystick.py（注释）、test_pins.py 豁免元组
- [x] 编译验证：`run_mq135_matrix.py` 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录；code-review 后中文提交（提交历史重构后随批次收尾同步，见 136b982d）
