# 03 — human_ir 模块（人体红外传感，手册 sensor--human-body-infrared-sensor.md）

**要做什么：** 模块库新增 `human_ir` 条目（仅 mspm0）：从手册提炼人体红外驱动为 **GPIO 迷你驱动**——页面 Get_HumanIR 返回 GET 宏 + header + main 完整（照 relay/human-body 提炼先例）。GPIO 输入实例（1 脚，上拉输入）。**极性定稿：感应到 = 输出高**——模块介绍「人进入其感应范围则输出高电平」+ 规格「电平输出：高3.3V/低0V」为准；页面函数注释「0=感应到、1=未感应到」与介绍/规格矛盾（疑与微波页同款复制，HC-SR501 器件标准高=检测到）→ 人工复核修正并记 notes（既定事实⑦，ir_remote 先例）；单宏 `HUMAN_IR_TRIGGER_LEVEL`（默认 1u = 引脚高=感应到）可切（照 ttp224 TTP224_TOUCH_LEVEL 先例，宏放 .h）。`human_ir_init()`（空实现占位——SYSCFG_DL_init() 生效，ttp224/ir_beam 先例）+ `human_ir_read()`（1=感应到人体）。

**被谁阻塞：** 无——可立即开始（与 01/02 独立；与 04 互相独立可并行）。

**状态：** resolved

**结论：** 2026-09-06 完成并提交（73d94cce）。人体红外 **GPIO 迷你驱动**（页面 Get_HumanIR 返回 GET 宏 + header + main 完整——照 relay/human-body 提炼先例）；母版 syscfg 新 GPIO 输入实例 HUMAN_IR（OUT 输入上拉，默认 PB8——与 STEP_MOTOR DCY2/SR04 ECHO/AT24C02 SDA 重叠：人体红外与步进/测距/存储不同框、同选概率最低，刻意不叠温湿度/光照/显示/语音/无线/按键/蜂鸣——感应灯/防盗标配组合）；`human_ir_init`（空实现占位——SYSCFG_DL_init() 生效）+ `human_ir_read`（1=感应到人体）；**极性定稿：感应到=输出高**——按模块介绍「人进入其感应范围则输出高电平」+ 规格「高3.3V/低0V」为准，页面函数注释「0=感应到」与介绍矛盾（疑与微波页同款复制，HC-SR501 器件标准高=检测到）→ 按 ir_remote 修正先例人工作复核、以介绍文字为准并记 notes；单宏 HUMAN_IR_TRIGGER_LEVEL（默认 1u）可切（照 ttp224 TTP224_TOUCH_LEVEL 先例，宏放 .h）；电平直读无去抖/无 GPIO 中断（GROUP1 仍被 motor 编码器独占）；页面模块特性（上电 1 分钟初始化/跳线触发/延时旋钮/避光避风/双元方向）记 notes 不落码；词表感知传感器 +人体红外传感器；单选生成 → SysConfig CLI → gmake 0 error/0 warning（verified=true）。

- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--human-body-infrared-sensor.md` 「代码块」章节抽完整 `bsp_HumanIR.c/h` → 改造为 `code/human_ir.c` + `code/human_ir.h`：去 main/printf、函数名规范化（`human_ir_init/human_ir_read`，去 `Get_HumanIR/GET` 命名）、GET 宏收敛为模块内读电平 + 极性宏判定
- [x] 母版 `mspm0.syscfg`：新 GPIO 输入实例 `HUMAN_IR`/OUT（direction INPUT、internalResistor PULL_UP，默认 PB8——与 STEP_MOTOR DCY2/SR04 ECHO/AT24C02 SDA 重叠：人体红外与步进/测距/存储不同框、同选概率最低，刻意不叠温湿度/光照/显示/语音/无线/按键/蜂鸣——感应灯/防盗标配组合；同选时经引脚绑定消解）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS：增 `"HUMAN_IR": ("human_ir",)`
- [x] `manifest.json`：`dependencies: []`；mspm0 平台条目（files/verified true/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接（资料 8888/案例 9p1o）+改造要点+**极性定稿说明（模块介绍/规格 = 感应到高电平；页面函数注释 0=感应到 与介绍矛盾已修正——按 HC-SR501 器件标准高=检测到，HUMAN_IR_TRIGGER_LEVEL 单宏可切：实物反相改 0）**+引脚直读无中断无去抖+上电 1 分钟初始化/跳线触发模式/避光避风说明+编译记录）；pins：`HUMAN_IR_OUT` = gpio_in 默认 PB8；简介判据：能力方向（人来灯亮/防盗报警/感应门/人流量检测）+ 无题绑定
- [x] wordlist.json 补录：「感知传感器」加「人体红外传感器（HC-SR501）」方案挂 `lib_modules: ["human_ir"]`，models 加 "人体红外传感器"
- [x] 测试：`tests/test_pins.py` MSPM0_DEFAULT_MAP 增 `("human_ir","HUMAN_IR_OUT") → ("HUMAN_IR","OUT")`；`tests/test_pin_bindings.py` 刻意表更新（PB8 3→4 注释补 human_ir）；`tests/test_syscfg_prune.py` HUMAN_IR 保留/裁剪断言；新增 `tests/test_module_human_ir.py`（manifest 结构（无依赖）+ 单选生成（syscfg 含 HUMAN_IR 输入上拉实例 + 模块文件落盘 + main.c 调 init/read 过静态门禁）+ 极性宏守卫（`HUMAN_IR_TRIGGER_LEVEL 1u` + `level == HUMAN_IR_TRIGGER_LEVEL`）+ notes 极性说明守卫 + 页面命名残留守卫）
- [x] 编译验证：`run_human_ir_matrix.py` 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录；code-review 后中文提交
