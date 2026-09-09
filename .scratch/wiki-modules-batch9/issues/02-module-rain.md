# 02 — rain 模块（雨滴传感器，手册 sensor--rain-sensor.md）

**要做什么：** 模块库新增 `rain` 条目（仅 mspm0）：从手册提炼雨滴驱动为纯驱动切片——ADC 模拟量读 AO 出 0-100% 雨量百分比。**ADC 薄封装**：依赖库内 adc 模块共享 ADC12_0 MEM0 槽位（默认 PA24/A0_3——无新通道/实例，照 mq2 方式）。`rain_init()` + `rain_read_percent()`（float 0-100%——**页面公式方向修正为正向映射 `value/4095×100`**：页面正文「雨水越大，电阻值越小，模拟值转化为的数字值越大」与页面原式 `(1−value/4095)×100` 矛盾（照原式雨越大百分比反而越低）→ 按「强度=水分覆盖=ADC 值关系」取证修正，notes 记录修正与依据；页面 3 次 × 100ms 间隔改 5 次快平均）；页面 ADC 中断改经 adc 模块 API 轮询（共享实例 IRQHandler 强符号唯一）；页面 DO（LM393 阈值）宏 `get_raindrop_do_value`/`GET_DO` 未用于演示 → 不声明 DO 角色；notes 写明非线性/干净度影响（雨滴板脏污/氧化/放置方式改变基线电阻——相对值非精标，「不同值对应降雨量多少毫米需实体测量」页面原话）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论：** 2026-09-09 完成并提交（87360a70）。雨滴 ADC 模拟量薄封装（mq2 方式——依赖 adc 模块共读 ADC12_0 MEM0、默认 PA24）；`rain_init` + `rain_read_percent` 出 0-100% 雨量百分比——**公式方向修正为正向映射 value/4095×100**（页面原式 (1−value/4095)×100 与页面正文「雨水越大，电阻值越小，模拟值转化为的数字值越大」矛盾——照原式雨越大百分比反而越低（疑同光敏页反向式复制残留），按「强度=水分覆盖=ADC 值关系」取证以正文为准修正，notes 记录修正与依据 + 实物若分压方向相反改公式一处）；页面 3 次 × 100ms 间隔与 get_adc_value 内 delay_ms(20) 去除改 5 次快平均；页面 ADC 中断改轮询（共享实例强符号唯一）；页面 DO 宏 `get_raindrop_do_value`/`GET_DO` 未用不声明；notes 写明非线性/干净度影响（基线电阻随脏污/氧化/放置方式变化——相对值非精标，页面原话「降雨量多少毫米需实体测量」）；词表感知传感器 +雨滴传感器；单选生成 → SysConfig CLI → gmake 0 error/0 warning（verified=true）；code-review 通过。

- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--rain-sensor.md` 「代码块」章节抽完整 `bsp_raindrop.c/h` → 改造为 `code/rain.c` + `code/rain.h`：去 main/printf、函数名规范化（`rain_init/read_percent`，去 `raindrop_config/ADC_GET/get_adc_value/get_raindrop_percentage_value` 命名）、**百分比公式方向修正**（正向 value/4095×100 + 注释/notes 写明页面原式矛盾与取证依据）、页面 ADC 中断改轮询、`get_raindrop_do_value`/`GET_DO` 不声明（mq2 同策略，notes）、页面 get_adc_value 内 delay_ms(20) 与百分比循环 delay_1ms(100) 去除（5 次快平均先例）
- [x] `manifest.json`：`dependencies: ["adc"]`；mspm0 平台条目（files/verified 初始 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接（资料 psfm/案例 6aqg）+改造要点+**公式方向修正与依据+非线性/干净度/毫米级换算需实体测量说明**）；pins：`RAIN_AO_CH0` = adc 默认 PA24 照 mq2；简介判据：能力方向（雨量检测/雨感联动）+ 无题绑定 + ADR 0009
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS：`ADC12_0` 元组增 `"rain"`（薄封装核对——无新实例）
- [x] wordlist.json 补录：「感知传感器」加「雨滴传感器（雨量检测）」方案挂 `lib_modules: ["rain"]`，models 加 "雨滴传感器"
- [x] 测试：新增 `tests/test_module_rain.py`（照 test_module_mq2.py：manifest 结构 + 单选生成（syscfg 保留 ADC12_0、模块文件落盘、main.c 调 init/read_percent 过静态门禁）+ 公式守卫（**正向映射 `/ (float)RAIN_ADC_MAX` 出现 + `1.0f - ` 不得出现在 percent 换算中——页面逆式回潮守卫**、`4095`/`100.0f`/`ADC_Channel_0`）+ 无 IRQHandler 守卫 + notes 守卫（「正向映射」「非线性」「实体测量」））；`tests/test_pins.py` 豁免元组增 `"rain"`；`tests/test_syscfg_prune.py` ADC12_0 新消费方断言；`tests/test_pin_bindings.py` PA24 注释补本批共读
- [x] 编译验证：`run_rain_matrix.py` 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录；code-review 后中文提交、工单 resolved


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
