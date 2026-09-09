# 01 — photoresistance 模块（光敏电阻传感器，手册 sensor--photoresistance-sensor.md）

**要做什么：** 模块库新增 `photoresistance` 条目（仅 mspm0）：从手册提炼光敏驱动为纯驱动切片——ADC 模拟量读 AO 出 0-100% 亮度百分比。**ADC 薄封装**：依赖库内 adc 模块共享 ADC12_0 MEM0 槽位（默认 PA24/A0_3，与 adc/us016/mq2 共读同槽——无新通道、无新 `$assign` 行、无新 syscfg 实例，照 mq2 方式）。`photoresistance_init()` + `photoresistance_read_percent()`（float 0-100%——页面 Get_illume_Percentage_value 原式 `(1 − value/4095)×100` **反向映射**（页面备注「最亮 100 最暗 0」自洽——光越强阻值越小、分压 ADC 值越小、百分比越高）、页面 10 次累加改 5 次快平均）；页面 ADC 中断（ADC12_0_INST_IRQHandler + gCheckADC 标志）改经 adc 模块 API 轮询（共享实例 IRQHandler 强符号唯一）；页面 DO（LM393 阈值）宏 `Get_DO_In`/`GET_DO_IN` 未用于演示 → 不声明 DO 角色；notes 写明与库内 bh1750（数字光照）的分工（光敏 = 廉价模拟件、非线性、需标定）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论：** 2026-09-09 完成并提交（3c63969d）。光敏电阻 ADC 模拟量薄封装（mq2 方式——依赖 adc 模块共读 ADC12_0 MEM0、默认 PA24，无新通道/实例/无新 $assign 行）；`photoresistance_init` + `photoresistance_read_percent` 出 0-100% 亮度百分比（页面原式反向映射（1−value/4095）×100——页面备注「最亮 100 最暗 0」自洽；页面 10 次累加改 5 次快平均）；页面 ADC 中断（IRQHandler + gCheckADC）改经 adc 模块 API 轮询（共享实例强符号唯一）；页面 DO（LM393 阈值）宏 `Get_DO_In`/`GET_DO_IN` 未用不声明；notes 写明非线性/需标定 + 与库内 bh1750 数字光照分工 + 页面「1MA」按 1mA 理解；词表感知传感器 +光敏电阻传感器；单选生成 → SysConfig CLI → gmake 0 error/0 warning（verified=true）；code-review（README 标准轴+规格轴）通过。

- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--photoresistance-sensor.md` 「代码块」章节抽完整 `bsp_illume.c/h` → 改造为 `code/photoresistance.c` + `code/photoresistance.h`：去 main/printf、函数名规范化（`photoresistance_init/read_percent`，去 `Illume_Init/ADC_GET/Get_Adc_Value/Get_illume_Percentage_value` 命名）、ADC 中断（IRQHandler + gCheckADC）改经 adc 模块 API 轮询（无 IRQHandler 强符号）、`Get_DO_In`/`GET_DO_IN` 不声明（mq2 同策略，notes）
- [x] `manifest.json`：`dependencies: ["adc"]`；mspm0 平台条目（files/verified 初始 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接（资料 y8jw/案例 ma8z）+改造要点+**反向映射（最亮 100 最暗 0）与非线性/需标定说明+与 bh1750 分工**）；pins：`PHOTORESISTANCE_AO_CH0` = adc 默认 PA24 照 mq2；简介判据：能力方向（光控调光/环境光强检测）+ 无题绑定 + ADR 0009
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS：`ADC12_0` 元组增 `"photoresistance"`（薄封装核对——无新实例）
- [x] wordlist.json 补录：「感知传感器」加「光敏电阻传感器（光控调光）」方案挂 `lib_modules: ["photoresistance"]`，models 加 "光敏电阻传感器"
- [x] 测试：新增 `tests/test_module_photoresistance.py`（照 test_module_mq2.py：manifest 结构 + 单选生成（syscfg 保留 ADC12_0、模块文件落盘、main.c 调 init/read_percent 过静态门禁）+ 公式守卫（`4095`/`100.0f`/`1.0f - ` 反向映射/`ADC_Channel_0`）+ 无 IRQHandler 守卫 + notes 守卫（「默最亮 100」「非线性」「bh1750」））；`tests/test_pins.py` 豁免元组增 `"photoresistance"`；`tests/test_syscfg_prune.py` ADC12_0 新消费方断言；`tests/test_pin_bindings.py` PA24 注释补本批共读
- [x] 编译验证：`run_photoresistance_matrix.py`（复制 run_joystick_matrix.py 改 slug）单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录；code-review 后中文提交、工单 resolved


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
