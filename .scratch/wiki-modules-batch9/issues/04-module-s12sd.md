# 04 — s12sd 模块（S12SD 紫外线传感器，手册 sensor--s12sd-uv-sensor.md）

**要做什么：** 模块库新增 `s12sd` 条目（仅 mspm0）：从手册提炼紫外线驱动为纯驱动切片——ADC 模拟量读 SIG 放大电压出 0-11 级 UV 指数。**ADC 薄封装**：依赖库内 adc 模块共享 ADC12_0 MEM0 槽位（默认 PA24/A0_3——无新通道/实例，照 mq2 方式）。`s12sd_init()` + `s12sd_read_uv_index()`（0-11 级——页面 Get_Ultraviolet_Intensity 阈值表原式（<227→0、227-317→1、318-407→2、408-502→3、503-605→4、606-695→5、696-794→6、795-880→7、881-975→8、976-1078→9、1079-1169→10、≥1170→11——0 低 11 高）、页面 SAMPLES 30×5ms 改 5 次快平均）；页面 ADC 中断改经 adc 模块 API 轮询（共享实例 IRQHandler 强符号唯一）；页面无 DO（3 Pin：VCC/GND/SIG）；notes 写明量程/UV-A 波段（检测波长 240-370nm——UV-B/UV-C 不响应、测量角度 130°、温漂 0.08%/℃、工作 2.7-5V/1mA、板载 LM358 放大；等级表按页面标定——页面实测室内 0 级，户外/遮挡/器件差异会偏移）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论：** 2026-09-09 完成并提交（d018fe80）。S12SD 紫外线 ADC 模拟量薄封装（mq2 方式——依赖 adc 模块共读 ADC12_0 MEM0、默认 PA24）；`s12sd_init` + `s12sd_read_uv_index` 出 0-11 级 UV 指数（页面 Get_Ultraviolet_Intensity 阈值表原式：<227→0、227-317→1、318-407→2、408-502→3、503-605→4、606-695→5、696-794→6、795-880→7、881-975→8、976-1078→9、1079-1169→10、≥1170→11——0 低 11 高；页面参数式 value 改模块内自读）；页面 SAMPLES 30×5ms 改 5 次快平均；页面 ADC 中断改轮询（共享实例强符号唯一）；页面无 DO（3 Pin：VCC/GND/SIG）；notes 写明量程/UV-A 波段（检测波长 240-370nm——UV-B/UV-C 不响应、测量角度 130°、温漂 0.08%/℃、工作 2.7-5V/1mA、板载 LM358 放大 1% 精度）与档位标定限制（页面实测室内 0 级——户外/遮挡/器件差异会偏移）；词表感知传感器 +紫外线传感器；单选生成 → SysConfig CLI → gmake 0 error/0 warning（verified=true）；code-review 通过。

- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--s12sd-uv-sensor.md` 「代码块」章节抽完整 `bsp_ultraviolet.c/h` → 改造为 `code/s12sd.c` + `code/s12sd.h`：去 main/printf、函数名规范化（`s12sd_init/read_uv_index`，去 `ULTRAVIOLET_Init/ADC_GET/Get_ADC_Value/Get_Ultraviolet_Intensity` 命名）、页面 ADC 中断改轮询、**UV 指数阈值表按页面原式保留**（12 档 0-11 级、阈值为 12bit ADC 值）、页面 SAMPLES 30×5ms 改 5 次快平均（delay_ms(5) 去除——快平均先例）
- [x] `manifest.json`：`dependencies: ["adc"]`；mspm0 平台条目（files/verified 初始 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接（资料 8888/案例 pri6）+改造要点+**量程/UV-A 波段（240-370nm）与档位标定限制**）；pins：`S12SD_AO_CH0` = adc 默认 PA24 照 mq2；简介判据：能力方向（紫外线强度/UV 指数检测）+ 无题绑定 + ADR 0009
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS：`ADC12_0` 元组增 `"s12sd"`（薄封装核对——无新实例）
- [x] wordlist.json 补录：「感知传感器」加「S12SD 紫外线传感器（UV 指数）」方案挂 `lib_modules: ["s12sd"]`，models 加 "紫外线传感器"
- [x] 测试：新增 `tests/test_module_s12sd.py`（照 test_module_mq2.py：manifest 结构 + 单选生成（syscfg 保留 ADC12_0、模块文件落盘、main.c 调 init/read_uv_index 过静态门禁）+ 公式守卫（阈值表常量 `227u`/`318u`/`408u`/`503u`/`606u`/`696u`/`795u`/`881u`/`976u`/`1079u`/`1170u` 档位——至少抽查首/末档 + `ADC_Channel_0`）+ 无 IRQHandler 守卫 + notes 守卫（「240-370nm」「UV-A」「11」））；`tests/test_pins.py` 豁免元组增 `"s12sd"`；`tests/test_syscfg_prune.py` ADC12_0 新消费方断言；`tests/test_pin_bindings.py` PA24 注释补本批共读
- [x] 编译验证：`run_s12sd_matrix.py` 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录；code-review 后中文提交、工单 resolved


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
