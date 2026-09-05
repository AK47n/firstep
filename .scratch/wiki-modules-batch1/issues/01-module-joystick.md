# 01 — joystick 模块（双轴摇杆 + 按键，手册 control--two-axis-keystroke-rocker-module.md）

**要做什么：** 模块库新增 `joystick` 条目（仅 mspm0）：从手册提炼完整摇杆驱动为纯驱动切片——双轴模拟量（X/Y）+ 按键（SW）读取，`joystick_init()` + 读轴（0-100% 或 12bit 原始值）+ 按键状态服务函数；选中后生成工程打开即可编译、可调用，不再"需自备"。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论：** 2026-09-05 完成并提交。关键发现（已写入母版注释与 manifest notes）：SysConfig ADC12 单发（single）模式只启用 `startAdd` 槽位，多 MEM 通道必须 `samplingOperationMode = "sequence"` + startAdd/endAdd——原 adc 模块注释「LQFP-64(PM) 无 adcPinN 槽位」系误判，2026-09-05 SysConfig CLI 实证；摇杆 X/Y 与 adc 模块共享 ADC12_0 实例（MEM1=PA26/A0_1、MEM2=PA25/A0_2，SW=PA9 上拉），单选生成 → gmake 0 error / 0 warning（PASS），全量 3362 测试通过。**code-review 收尾修正**：adc 模块 manifest notes + adc_mspm0.c 注释与共享事实同步（原「MEM1 未绑引脚、adc_channel=1 返回 0」已过时——MEM1 现为摇杆同读通道，文档按 sequence 三通道 + 共享语义更正）。

- [ ] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/control--two-axis-keystroke-rocker-module.md` 「代码块」章节抽完整 `bsp_*.c/h` → 改造为 `code/joystick.c` + `code/joystick.h`：去 main/printf、函数名规范化（`joystick_init/joystick_read_x/joystick_read_y/joystick_read_sw`）、全局缓存改出参或封装读数、ADC 断点中断改轮询（无状态机，ADR 0009）
- [ ] 两轴读取决策：首选依赖库内 `adc` 模块（`dependencies: ["adc"]`）读 MEM0/MEM1 双通道；若 adc 模块接口只覆盖单通道，则在**本工单内**扩展 adc 模块（通道参数化 + 补其生成级测试，不动其他既有用例）
- [ ] 母版 `mspm0.syscfg`：GPIO 实例（SW 输入，1 associatedPin，上拉、低有效——按键 KEY 先例；若两轴走 adc 模块则不加 ADC 通道，仅在 ADC12_0 注释注明摇杆占用）；默认脚按"同选概率最低重叠"规则选，与既有默认重叠对登记 `test_pin_bindings` 刻意表
- [ ] `syscfg_instances.py` INSTANCE_CONSUMERS 登记
- [ ] `manifest.json`：`dependencies: ["delay"(若用), "adc"(若走)]`；mspm0 平台条目（files/verified 初 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接+改造要点+编译记录）；pins：SW = gpio_in（default 按分配），XY 按 adc 依赖注明通道；简介判据：与代码一致 + 能力方向（手动控制/模拟量遥控/参数调节）+ 无题绑定（过 BANNED_TOPIC_WORDS 拦截）
- [ ] wordlist.json 补录：「按键/遥控」类加「双轴摇杆」方案挂 `lib_modules: ["joystick"]`
- [ ] 测试：`tests/test_pins.py::MSPM0_DEFAULT_MAP` 增映射；`test_syscfg_prune.py` 增 JOYSTICK 实例断言；新增 `tests/test_module_joystick.py`（单选生成 → syscfg 含实例 + 文件落盘 + main.c 调 init/服务函数过静态门禁）
- [ ] 编译验证：module-polish 编译矩阵配方 gmake 真编译 0 error、模块自身 warning 0；结果回写 manifest verified=true + notes 记录；code-review 后提交
