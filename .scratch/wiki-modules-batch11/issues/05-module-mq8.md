# 05 — mq8 模块（MQ-8 氢气传感器，手册 sensor--mq-8-sensor.md）

**要做什么：** 模块库新增 `mq8` 条目（仅 mspm0）：从手册提炼 MQ-8 驱动为纯驱动切片——ADC 模拟量读 AO 出 0-100% 相对浓度。**ADC 薄封装**（mq2 方式，同 mq3/04/06/07 同构照抄，差异仅检测对象/页面函数名/演示串）：依赖库内 adc 模块共享 ADC12_0 MEM0 槽位（默认 PA24/A0_3，无新通道、无新 `$assign` 行、无新 syscfg 实例）。`mq8_init()` + `mq8_read_percent()`（页面 Get_MQ8_Percentage_value 原式 `value/4095×100` **正向映射**——正文「电导率随氢气浓度增加而增大」，与 mq2 定稿方向一致；页面 30×5ms 改 5 次快平均）；页面 ADC 中断改经 adc 模块 API 轮询；页面 DO（LM393 阈值）宏 `Get_MQ8_DO_value`/`MQ_DO` 未用于演示 → 不声明 DO 角色；notes 写明 MQ 系相对值非 ppm 精标 + 预热/湿度影响 + 多路气体同选共读 MEM0 现实约束。

**被谁阻塞：** 无——可立即开始（与 01-04/06-07 独立）。

**状态：** resolved

**结论：** 2026-09-11 完成并提交。ADC 薄封装（依赖 adc 模块共享 ADC12_0 MEM0，默认 PA24，无新 $assign 行）；mq8_init + mq8_read_percent（value/4095×100 正向映射页面原式）；页面 ADC 中断改轮询；页面 Get_MQ8_DO_value/MQ_DO 未用于演示不声明 DO 角色；notes 写明 MQ 系相对值非 ppm + 预热/湿度 + 多路气体同选共读 MEM0 限制 + 页面函数注释「酒精值」模板残留错字（本件应为氢气）记录；单选生成 → SysConfig CLI → gmake 0 error/0 warning（PASS，verified=true）；**code-review 随机深审件（标准+规格双轴通过，见 spec 实施结论）**；未上板。

**验收：**

- [ ] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--mq-8-sensor.md` 「代码块」章节抽完整 `bsp_mq8.c/h` → 改造为 `code/mq8.c` + `code/mq8.h`：去 main/printf、函数名规范化（`mq8_init/read_percent`）、ADC 中断改经 adc 模块 API 轮询（无 IRQHandler 强符号）、`Get_MQ8_DO_value`/`MQ_DO` 不声明（mq2 同策略，notes）
- [ ] `manifest.json`：`dependencies: ["adc"]`；mspm0 平台条目（files/verified 初始 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接（资料 9966/案例 kpr3）+改造要点+**正向映射取证**+**MQ 系相对值非 ppm 精标+预热/湿度影响**+**多路气体同选共读 MEM0 现实约束**）；pins：`MQ8_AO_CH0` = adc 默认 PA24 照 mq2；简介判据：能力方向（氢气检测、氢能源安全监测、浓度报警）+ 无题绑定 + ADR 0009
- [ ] `syscfg_instances.py` INSTANCE_CONSUMERS：`ADC12_0` 元组增 `"mq8"`（薄封装核对——无新实例）
- [ ] wordlist.json 补录：「感知传感器」加「MQ-8 氢气传感器」方案挂 `lib_modules: ["mq8"]`，models 加 "MQ-8"
- [ ] 测试：新增 `tests/test_module_mq8.py`（照 test_module_mq2.py：manifest 结构 + 单选生成 + 公式守卫（`MQ8_ADC_MAX`/`4095u`/`* 100.0f`/`ADC_Channel_0`）+ 无 IRQHandler 守卫 + notes 守卫）；`tests/test_pins.py` 豁免元组增 `"mq8"`；`tests/test_syscfg_prune.py` ADC12_0 新消费方断言；`tests/test_pin_bindings.py` PA24 注释补本批共读
- [ ] 编译验证：`run_mq8_matrix.py` 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录；code-review 后中文提交、工单 resolved
