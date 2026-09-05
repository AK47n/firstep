# 02 — us016 模块（US-016 模拟量超声波测距，手册 sensor--us-016-ultrasonic-ranging-sensor.md）

**要做什么：** 模块库新增 `us016` 条目（仅 mspm0）：从手册提炼完整"ADC 电压→距离"驱动为纯驱动切片——**依赖 adc 模块 MEM0 的薄封装**：`us016_init()` + `us016_read_distance_cm()`（float 出 cm，5 次快速平均，3m 量程公式 L=(A×3072/4096)×(Vref/Vcc)mm）；选中后生成工程打开即可编译，不再"需自备"。

**被谁阻塞：** 无——可立即开始（与 01/03 独立）。

**状态：** pending

**结论：** 待完成。

- [ ] 通道决策（既定事实：ADC12_0 已是 sequence 三通道 endAdd=2，MEM0=adc/MEM1-2=joystick）：**优先薄封装**——依赖 adc 模块读 MEM0（adc_get(ADC_1, ADC_Channel_0)），不新开通道；若实现中发现薄封装不可行（冲突不可消解）→ 才走独立通道（sequence 加 MEM endAdd+1 + 同步 joystick 相关测试断言），本件预计不走
- [ ] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--us-016-ultrasonic-ranging-sensor.md` 「代码块」章节抽完整 `bsp_US016.c/h` → 改造为 `code/us016.c` + `code/us016.h`：去 main/printf、函数名规范化（`us016_init/read_distance_cm`）、ADC 中断（IRQHandler + gCheckADC 标志位）改轮询（照 adc/joystick 先例——共享 ADC12_0 实例，多模块同选时 IRQHandler 强符号重复定义；`dependencies: ["adc"]`）
- [ ] 换算：公式 L=(A×3072/4096)×(Vref/Vcc)mm（手册正文「3096」与代码「3072」不一，按代码 0.75 系数并 notes 注明）；RANGE 保留为编译期宏（US016_RANGE_1M，0=3m 默认，1=1m 系数 0.25）；50 次×delay_ms(10) 平均改 5 次快速平均（joystick 先例，notes 注明真机行为差异）
- [ ] 共享事实同步（batch1 收尾未竟）：`library/modules/adc/code/adc_mspm0.h` 中「MEM1 未绑引脚、v1 不可用——LQFP-64(PM) 无 adcPinN 槽位」已过时（MEM1=joystick X 共享、sequence 实证）→ 按 manifest notes + .c 的 2026-09-05 更正口径同步；adc manifest notes 增 us016 共享说明（MEM0 现归 adc+us016 薄封装共读）
- [ ] 默认脚：无新 $assign 行——us016 角色默认脚 = MEM0 槽位脚 PA24（与 adc 模块同槽共享，属"共享槽位"非刻意重叠；PA24 计数不变，`test_pin_bindings` 刻意表注释注明 us016）；手册原脚 PA27 经绑定即可复现（绑 PA27 → adcPin3→adcPin0 + adcMem0chansel→CHAN_0，notes 注明）
- [ ] `syscfg_instances.py` INSTANCE_CONSUMERS：`"ADC12_0": ("adc", "joystick", "us016", "ir_distance")`（ir_distance 在第 04 件加，此件先加 us016）
- [ ] `manifest.json`：`dependencies: ["adc"]`；mspm0 平台条目（files/verified 初 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接+改造要点+编译记录）；pins：US016_OUT_CH0 = adc（default PA24，尾 `_CH0` 推导 MEM0）；简介判据：能力方向（模拟量测距/避障/定高）+ 无题绑定
- [ ] wordlist.json 补录：「感知传感器」加「模拟量超声波测距（US-016）」方案挂 `lib_modules: ["us016"]`；models 加 "US-016"
- [ ] 测试：新增 `tests/test_module_us016.py`（manifest 结构：dependencies=(adc,) 单角色 adc PA24 + 单选生成：syscfg 保留 ADC12_0 + adc 模块文件落盘 + us016 文件落盘 + main.c 调 init/read 过静态门禁）；`test_pin_bindings.py` PA24 注释更新；`test_syscfg_prune.py` 增 ADC12_0 由 us016 保留断言
- [ ] 编译验证：复制 `run_joystick_matrix.py` 改 slug 为 us016 → gmake 真编译 0 error、模块自身 warning 0；结果回写 manifest verified=true + notes 记录；code-review 后中文提交
