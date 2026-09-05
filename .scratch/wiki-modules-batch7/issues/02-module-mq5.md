# 02 — mq5 模块（MQ-5 液化气/天然气传感器，手册 sensor--mq-5-sensor.md）

**要做什么：** 模块库新增 `mq5` 条目（仅 mspm0）：从手册提炼 MQ-5 驱动为纯驱动切片——ADC 模拟量读 AO 出 0-100% 相对浓度。**同 mq135 独立 MEM 模式**（批量同构照抄 mq135 工单，差异仅在页面 ADC 倍数/注释与 wordlist 名称）：ADC12_0 sequence 开 MEM5（endAdd 4→5、adcMem5chansel=CHAN_5、adcPin5=PB24）。`mq5_init()` + `mq5_read_percent()`（4095/100 原式、5 次快平均照 mq2）；页面 ADC 中断改轮询；notes 同 mq135 模板（通道方案差异 + MQ 系相对值非 ppm 精标 + 预热）。

**被谁阻塞：** 01 mq135（同构打样 + adc 模块扩展已随 01 完成；本件可随后或并行照抄）。

**状态：** resolved

**结论：** 2026-09-08 完成并提交（9f818c83）。ADC 模拟量独立 MEM5 通道（同 mq135 独立 MEM 模式——多路气体同选时物理通道独立、无共读冲突）；母版 syscfg ADC12_0 sequence 加第 6 通道（endAdd 4→5、adcMem5chansel=CHAN_5、adcPin5=PB24——选 PB24 不选 PA14（板载 LED2+15k 负载不适合作 ADC 输入）与 PA22（调试/巡线/无线/触摸与气体检测同框概率更高））；`mq5_init` + `mq5_read_percent` 出 0-100% 相对浓度（页面 4095/100 原式、30 次→5 次快平均）；页面 ADC 中断改经 adc 模块 API 轮询；页面 DO 宏未用不声明；notes 写明与 mq2 的通道方案差异与 MQ 系相对值非 ppm 精标+预热限制；词表感知传感器 +MQ-5；单选生成 → SysConfig CLI → gmake 0 error/0 warning（verified=true）；code-review 双轴通过（收尾修正见 136b982d）。

- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--mq-5-sensor.md` 「代码块」章节抽完整 `bsp_mq5.c/h` → 改造为 `code/mq5.c` + `code/mq5.h`：去 main/printf、函数名规范化（`mq5_init/mq5_read_percent`，去 `ADC_MQ5_Init/Get_Adc_MQ5_Value/Get_MQ5_Percentage_value` 命名）、ADC 中断改经 adc 模块 API 轮询、`MQ_DO`/`Get_MQ5_DO_value` 不声明（mq2/mq135 同策略，notes）
- [x] 母版 `mspm0.syscfg`：ADC12_0 sequence 加第 6 通道——`endAdd 4→5`、`adcMem5chansel="DL_ADC12_INPUT_CHAN_5"`、`adcPin5.$assign="PB24"`；ADC 段注释同步（五通道 → 六通道、MEM5 归 mq5）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS：`ADC12_0` 元组增 `"mq5"`
- [x] `manifest.json`：`dependencies: ["adc"]`；mspm0 平台条目（files/verified true/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接（资料 9966/案例 kddp）+改造要点+**与 mq2 通道方案差异**+**MQ 系相对值非 ppm 精标+预热**+编译记录）；pins：`MQ5_AO_CH5` = adc 默认 PB24；简介判据：能力方向（可燃气体/液化气/天然气检测、浓度报警）+ 无题绑定
- [x] wordlist.json 补录：「感知传感器」加「MQ-5 液化气/天然气传感器」方案挂 `lib_modules: ["mq5"]`，models 加 "MQ-5"
- [x] 测试：`tests/test_pin_bindings.py` 刻意表更新（PB24 4→5 注释补 mq5）；`tests/test_syscfg_prune.py` ADC12_0 新消费方（mq5）断言；新增 `tests/test_module_mq5.py`（manifest 结构 + 单选生成 + 公式守卫（4095/100.0f/ADC_Channel_5）+ 无 IRQHandler 守卫）；**旧断言同步**：test_module_ir_distance.py（endAdd 4→5）、test_module_joystick.py（注释）、test_module_mq135.py（endAdd 5）
- [x] 编译验证：`run_mq5_matrix.py` 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录；code-review 后中文提交
