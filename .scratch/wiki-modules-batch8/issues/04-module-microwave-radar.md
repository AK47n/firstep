# 04 — microwave_radar 模块（微波多普勒雷达，手册 sensor--microwave-doppler-radar-sensor.md）

**要做什么：** 模块库新增 `microwave_radar` 条目（仅 mspm0）：从手册提炼微波雷达驱动为 **GPIO 迷你驱动**——页面 OUTPIN_Scanf 返回 OUT_IN 宏 + header + main 完整；页面 main 演示含开/关门时序逻辑（flag/time 计时、2000ms 关门）——**归生成骨架**（ADR 0009），模块只出 `microwave_radar_init()` + `microwave_radar_read()`（1=检测到移动）。**极性按页面（自一致）**：页面注释 + main 演示均按「0=检测到物体移动、1=未检测到」（`if (OUTPIN_Scanf() == 0)` 判移动）——默认沿用页面（低=检测到），单宏 `MICROWAVE_TRIGGER_LEVEL`（默认 0u = 引脚低=检测到）可切（照 ttp224 TTP224_TOUCH_LEVEL 先例，宏放 .h；实物输出反相改 1）。GPIO 输入实例 1 脚（上拉输入）。

**被谁阻塞：** 无——可立即开始（与 01/02/03 独立可并行）。

**状态：** ready-for-agent

- [ ] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--microwave-doppler-radar-sensor.md` 「代码块」章节抽完整 `bsp_mh100x.c/h` → 改造为 `code/microwave_radar.c` + `code/microwave_radar.h`：去 main/printf/DEMO 时序（开/关门逻辑归骨架）、函数名规范化（`microwave_radar_init/microwave_radar_read`，去 `OUTPIN_Scanf/OUT_IN` 命名）、OUT_IN 宏收敛为模块内读电平 + 极性宏判定
- [ ] 母版 `mspm0.syscfg`：新 GPIO 输入实例 `MICROWAVE`/OUT（direction INPUT、internalResistor PULL_UP，默认 PA0——与 I2C_0 SDA（姿态）/IR_TX OUT（红外发射）重叠：微波雷达与姿态采集/红外发射链不同框、同选概率最低；PA0 板载 LED 共用——微波默认低=检测到，检测时板载 LED 点亮可作直观指示（ir_remote_tx 先例同款）；软 I2C 件避让 PA0/PA1 的 i2c_bus_share 先例与本件无关（纯 GPIO 输入）；同选时经引脚绑定消解）
- [ ] `syscfg_instances.py` INSTANCE_CONSUMERS：增 `"MICROWAVE": ("microwave_radar",)`
- [ ] `manifest.json`：`dependencies: []`；mspm0 平台条目（files/verified false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接（资料 2cz6/案例 86is）+改造要点+**极性按页面（0=检测到——页面注释与演示自一致；MICROWAVE_TRIGGER_LEVEL 单宏可切：实物输出反相改 1）**+**页面开/关门时序演示归生成骨架（ADR 0009）**+多普勒原理/5V 供电/2-16m 连续可调/不受温度影响说明+编译记录）；pins：`MICROWAVE_OUT` = gpio_in 默认 PA0；简介判据：能力方向（自动门/车流检测/倒车雷达/移动感应报警）+ 无题绑定
- [ ] wordlist.json 补录：「感知传感器」加「微波雷达传感器（HB100）」方案挂 `lib_modules: ["microwave_radar"]`，models 加 "微波雷达传感器"
- [ ] 测试：`tests/test_pins.py` MSPM0_DEFAULT_MAP 增 `("microwave_radar","MICROWAVE_OUT") → ("MICROWAVE","OUT")`；`tests/test_pin_bindings.py` 刻意表更新（PA0 2→3 注释补 microwave_radar）；`tests/test_syscfg_prune.py` MICROWAVE 保留/裁剪断言；新增 `tests/test_module_microwave_radar.py`（manifest 结构（无依赖）+ 单选生成（syscfg 含 MICROWAVE 输入上拉实例 + 模块文件落盘 + main.c 调 init/read 过静态门禁）+ 极性宏守卫（`MICROWAVE_TRIGGER_LEVEL 0u`——页面低=检测到 + `level == MICROWAVE_TRIGGER_LEVEL`）+ read 语义守卫（1=检测到移动）+ notes 守卫（演示时序归骨架））
- [ ] 编译验证：`run_microwave_radar_matrix.py` 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录；code-review 后中文提交
