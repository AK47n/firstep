# 01 — mq3 模块（MQ-3 酒精/汽油蒸汽传感器，手册 sensor--mq-3-sensor.md）

**要做什么：** 模块库新增 `mq3` 条目（仅 mspm0）：从手册提炼 MQ-3 驱动为纯驱动切片——ADC 模拟量读 AO 出 0-100% 相对浓度。**ADC 薄封装**（mq2 方式）：依赖库内 adc 模块共享 ADC12_0 MEM0 槽位（默认 PA24/A0_3，与 adc/us016/mq2/批次 9 四件共读同槽——无新通道、无新 `$assign` 行、无新 syscfg 实例）。`mq3_init()` + `mq3_read_percent()`（float 0-100%——页面 Get_MQ3_Percentage_value 原式 `value/4095×100` **正向映射**，正文「电导率随酒精蒸气浓度增加而增大」同向，与 mq2 定稿方向一致；页面 30×5ms 改 5 次快平均）；页面 ADC 中断（ADC12_0_INST_IRQHandler + gCheckADC 标志）改经 adc 模块 API 轮询（共享实例 IRQHandler 强符号唯一）；页面 DO（LM393 阈值）宏 `Get_MQ3_DO_value`/`MQ_DO` 未用于演示 → 不声明 DO 角色；notes 写明 MQ 系相对值非 ppm 精标 + 预热/湿度影响 + 多路气体同选共读 MEM0 现实约束。

**被谁阻塞：** 无——可立即开始（与 02-07 独立）。

**状态：** resolved

**结论：** 2026-09-11 完成并提交。ADC 薄封装（依赖 adc 模块共享 ADC12_0 MEM0，默认 PA24，无新 $assign 行）；mq3_init + mq3_read_percent（5 次快平均 → value/4095×100 出 0-100% 相对浓度——正向映射页面原式+正文取证，与 mq2 定稿方向一致）；页面 ADC 中断（IRQHandler + gCheckADC）改依赖 adc 模块轮询（共享实例强符号唯一）；页面 Get_MQ3_DO_value/MQ_DO（LM393 阈值）未用于演示不声明 DO 角色；默认 PA24 与批次 5 tcs34725 SDA 重叠系 MEM0 槽位唯一所致；notes 写明 MQ 系相对值非 ppm 精标 + 预热 3-5 分钟/湿度影响 + 多路气体同选共读 MEM0 物理通道限制（MEM 8/8 已满）+ 手册原脚 PA27 绑定复现；词表感知传感器 +MQ-3；单选生成 → SysConfig CLI → gmake 0 error/0 warning（PASS，verified=true）；code-review 双轴通过（同构对仗核对；本件非随机深审件）；未上板。

**验收：**

- [ ] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--mq-3-sensor.md` 「代码块」章节抽完整 `bsp_mq3.c/h` → 改造为 `code/mq3.c` + `code/mq3.h`：去 main/printf、函数名规范化（`mq3_init/read_percent`，去 `ADC_MQ3_Init/ADC_GET/Get_Adc_MQ3_Value/Get_MQ3_Percentage_value` 命名）、ADC 中断（IRQHandler + gCheckADC）改经 adc 模块 API 轮询（无 IRQHandler 强符号）、`Get_MQ3_DO_value`/`MQ_DO` 不声明（mq2 同策略，notes）
- [ ] `manifest.json`：`dependencies: ["adc"]`；mspm0 平台条目（files/verified 初始 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接（资料 9966/案例 yk3j）+改造要点+**正向映射取证**+**MQ 系相对值非 ppm 精标+预热/湿度影响**+**多路气体同选共读 MEM0 现实约束**）；pins：`MQ3_AO_CH0` = adc 默认 PA24 照 mq2；简介判据：能力方向（酒精/汽油蒸汽检测、酒驾呼气检测、浓度报警）+ 无题绑定 + ADR 0009
- [ ] `syscfg_instances.py` INSTANCE_CONSUMERS：`ADC12_0` 元组增 `"mq3"`（薄封装核对——无新实例）
- [ ] wordlist.json 补录：「感知传感器」加「MQ-3 酒精/汽油蒸汽传感器」方案挂 `lib_modules: ["mq3"]`，models 加 "MQ-3"
- [ ] 测试：新增 `tests/test_module_mq3.py`（照 test_module_mq2.py：manifest 结构 + 单选生成（syscfg 保留 ADC12_0、模块文件落盘、main.c 调 init/read_percent 过静态门禁）+ 公式守卫（`MQ3_ADC_MAX`/`4095u`/`* 100.0f`/`ADC_Channel_0`）+ 无 IRQHandler 守卫 + notes 守卫（「相对值」「ppm」「预热」））；`tests/test_pins.py` 豁免元组增 `"mq3"`；`tests/test_syscfg_prune.py` ADC12_0 新消费方断言；`tests/test_pin_bindings.py` PA24 注释补本批共读
- [ ] 编译验证：`run_mq3_matrix.py`（复制 run_mq2_matrix.py 改 slug）单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录；code-review 后中文提交、工单 resolved
