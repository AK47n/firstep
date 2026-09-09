# 07 — ms1100 模块（MS1100 VOC 气体传感器，手册 sensor--ms1100-gas-sensor.md）

**要做什么：** 模块库新增 `ms1100` 条目（仅 mspm0）：从手册提炼 MS1100 驱动为纯驱动切片——ADC 模拟量读 AOUT 出 0-100% 相对浓度。**ADC 薄封装**（mq2 方式）：依赖库内 adc 模块共享 ADC12_0 MEM0 槽位（默认 PA24/A0_3，无新通道、无新 `$assign` 行、无新 syscfg 实例）。`ms1100_init()` + `ms1100_read_percent()`（0-100% 相对浓度——**页面无百分比函数，由页面 demo 电压原式推导**：`voltage=(value/4095)×3.3` → `percent=voltage/3.3×100=value/4095×100`（Vref 3.3V 满量程归一；**正向映射**——正文「AOUT 为气体量对应电压值、清洁空气电压 <1V」）；页面 30×3ms 改 5 次快平均）；页面 ADC 中断改经 adc 模块 API 轮询；页面 DO（LM393 阈值比较）宏 `Get_DO_Num`/`MS1100_DO` 未用于演示 → 不声明 DO 角色；notes 写明 MS1100 相对值非 ppm 精标 + **预热 3-5 分钟（页面原文）** + 多路气体同选共读 MEM0 现实约束 + 与 SGP30/AGS10（ppb/ppm 数字量）及 MQ 系分工。

**被谁阻塞：** 无——可立即开始（与 01-06 独立）。

**状态：** resolved

**结论：** 2026-09-11 完成并提交。ADC 薄封装（依赖 adc 模块共享 ADC12_0 MEM0，默认 PA24，无新 $assign 行）；ms1100_init + ms1100_read_percent（value/4095×100——**页面无百分比函数**，由页面 demo 电压式 value/4095×3.3 推导归一（Vref 3.3V），正向映射正文取证「AOUT 随气体量变化、清洁空气 <1V」；5 次快平均——页面 30×3ms）；页面 ADC 中断改轮询；页面 Get_DO_Num/MS1100_DO 未用于演示不声明 DO 角色（页面仅述可调电阻比较——无 LM393 依据）；notes 写明相对值非 ppm 精标 + **预热 3-5 分钟（页面原文）** + 多路气体同选共读 MEM0 限制 + 与 sgp30/ags10（ppb/ppm 数字量）及 MQ 系分工；词表感知传感器 +MS1100；单选生成 → SysConfig CLI → gmake 0 error/0 warning（PASS，verified=true）；**code-review 随机深审件（标准+规格双轴通过，见 spec 实施结论）**；未上板。

**验收：**

- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--ms1100-gas-sensor.md` 「代码块」章节抽完整 `bsp_ms1100.c/h` → 改造为 `code/ms1100.c` + `code/ms1100.h`：去 main/printf、函数名规范化（`ms1100_init/read_percent`，去 `MS1100_Init/ADC_GET/Get_ADC_Value` 命名）、ADC 中断（IRQHandler + gCheckADC）改经 adc 模块 API 轮询（无 IRQHandler 强符号）、`Get_DO_Num`/`MS1100_DO` 不声明（mq2 同策略，notes）
- [x] `manifest.json`：`dependencies: ["adc"]`；mspm0 平台条目（files/verified 初始 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接（资料 ixqv/案例 2ale）+改造要点+**read_percent 推导说明（页面无百分比函数，电压式 value/4095×3.3 归一）**+**正向映射取证**+**相对值非 ppm 精标+预热 3-5 分钟**+**多路气体同选共读 MEM0 现实约束**+**与 sgp30/ags10/mq 系分工**）；pins：`MS1100_AO_CH0` = adc 默认 PA24 照 mq2；简介判据：能力方向（VOC/甲醛/苯系检测、室内空气质量监测、浓度报警）+ 无题绑定 + ADR 0009
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS：`ADC12_0` 元组增 `"ms1100"`（薄封装核对——无新实例）
- [x] wordlist.json 补录：「感知传感器」加「MS1100 VOC 气体传感器（甲醛/苯系）」方案挂 `lib_modules: ["ms1100"]`，models 加 "MS1100"
- [x] 测试：新增 `tests/test_module_ms1100.py`（照 test_module_mq2.py：manifest 结构 + 单选生成 + 公式守卫（`MS1100_ADC_MAX`/`4095u`/`* 100.0f`/`ADC_Channel_0`）+ 无 IRQHandler 守卫 + notes 守卫（「相对值」「ppm」「预热」「VOC」或「甲醛」））；`tests/test_pins.py` 豁免元组增 `"ms1100"`；`tests/test_syscfg_prune.py` ADC12_0 新消费方断言；`tests/test_pin_bindings.py` PA24 注释补本批共读
- [x] 编译验证：`run_ms1100_matrix.py` 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录；code-review 后中文提交、工单 resolved


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
