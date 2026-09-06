# 03 — l298n 大电流电机驱动（PWM+GPIO，手册 control--l298n-motor-drive-module.md）

**要做什么：** 模块库新增 `l298n` 条目（仅 mspm0，独立模块不并入 motor）：从手册提炼 L298N 驱动为纯驱动切片——方向+调速形态（页面 AO_Control 原样：IN1=C0/IN2=C1 双通道 PWM，dir=1 → C0=0/C1=duty、dir=0 → C0=duty/C1=0）+ EN 使能 GPIO（三脚一组 IN1/IN2/EN），API 对齐库风格 `l298n_init()` + `l298n_set_duty()` + `l298n_set_direction()`；母版新 PWM 实例 `L298N_PWM`（TIMG12 默认，与 step_motor 互替低同选；裁剪后独占，同选换实例消解）+ GPIO 实例 `L298N`（EN）；与 motor(TB6612) 分工与适用场景（大电流/多路电机、无编码器闭环）记 notes；选中后生成工程打开即可编译、可调用。

**被谁阻塞：** 无——可立即开始（与 01/02/04 独立）。

**状态：** resolved

**结论：** 2026-09-11 完成并提交。独立 l298n 模块（不并入 motor——接线/芯片/场景差异大）；AO_Control 按页面原样拆为 l298n_set_direction（1 正转/0 反转页面 dir 语义）+ l298n_set_duty（0~per-1 限幅）——内部保留 duty、方向切换重应用（与页面逐拍等价）；母版 PWM 实例 L298N_PWM = TIMG12（**与 DCC_100_PWM2 同外设——L298N 与步进驱动互替、同选概率最低故叠，同选时经引脚绑定换实例消解**；clockPrescale=1 + timerCount=2000，32MHz/2000 ≈ 16kHz）C0=PA14/C1=PB24 + GPIO 实例 L298N/EN 默认 PA27（使能高有效，页面「5V 使能高有效，PWM 调速取跳线帽」）；页面 DL_TimerG_setCaptureCompareValue 按 motor.c 先例改 DL_Timer_setCaptureCompareValue（SDK 2.11 同义）；刻意与 motor 默认 10 脚错开（两驱动可能并排使用）；单路 A 端口范围（页面仅 A 端口演示，B 端口同构扩展留后续）；与 motor(TB6612) 分工（1.2A 轻量带编码器闭环 vs 2A 大电流无编码器——平衡车/推车/闸机/重载）写入 notes；syscfg_model.py pwm 落点匹配按 slug 反查实例扩展（DCC_100_PWM2/L298N_PWM 同脚区分——含直接判例测试）；单选生成 → SysConfig CLI（TIMG12/PA14/PB24/PA27 实证合法）→ gmake 0 error/0 warning（PASS，verified=true）；词表执行机构 L298N 方案补 lib_modules。未上板。code-review（随批次 10 收尾两轴评审）。

- [x] 代码提炼：手册「代码块」抽 `bsp_L298N.c/h` → `code/l298n.c` + `code/l298n.h`：去 main/printf、`AO_Control(dir,speed)` → `l298n_set_direction(dir)` + `l298n_set_duty(duty)`（内部保留 duty 状态，方向切换重应用——页面对应函数语义等价拆分）、页面 `DL_TimerG_setCaptureCompareValue` 按 motor.c 先例改 `DL_Timer_setCaptureCompareValue`（SDK 2.11 同义 API）
- [x] 母版 `mspm0.syscfg`：新 PWM 实例 `L298N_PWM`（TIMG12、clockPrescale=1、timerCount=2000（≈16kHz——32MHz BUSCLK）、C0=PA14/C1=PB24、CHANNEL_0/1 $name 唯一、dutyCycle=0；与 DCC_100_PWM2 同外设——L298N 与步进驱动互替、同选概率最低，同选时经引脚绑定换实例消解）+ 新 GPIO 实例 `L298N`（EN 输出初始 SET，默认 PA27——与 HUIDU R2/ADC12_0 adcPin0/TTP224 OUT4 重叠：使能脚与巡线/测距/触摸不同框、同选概率最低）；与 motor 默认 10 脚刻意错开（两驱动可能并排使用），注释写明
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"L298N_PWM": ("l298n",)` / `"L298N": ("l298n",)`
- [x] `manifest.json`：dependencies []；mspm0 平台条目；pins L298N_PWM_C0/L298N_PWM_C1（pwm，default PA14/PB24）+ L298N_EN（gpio_out，default PA27）；kit+source_url（手册原页+采购链接）；notes 含手册路径+原页+网盘链接+改造要点+单路（A 端口）范围说明+与 motor(TB6612) 分工（L298N = 2A 大电流双 H 桥/压降 ~1.5V/发热大/无编码器脚，motor = TB6612 1.2A 轻量带编码器闭环）——verified 转 true
- [x] wordlist.json：「执行机构」L298N 方案补 `lib_modules: ["l298n"]` + note 更新（已打通）+ models 加 L298N
- [x] 测试：`test_pins.py::MSPM0_DEFAULT_MAP` 增 3 行；`test_pin_bindings.py` 刻意表 PA14/PB24/PA27 + TIMG12 行；`test_syscfg_prune.py` 增 L298N_PWM/L298N 断言；新增 `tests/test_module_l298n.py`：manifest 结构（roles/defaults）+ 单选生成（syscfg 含 L298N_PWM/L298N、文件落盘、main.c 调 init/set_duty/set_direction 过静态门禁）+ dir 语义守卫（C0=0/C1=duty 形态）+ `DL_Timer_setCaptureCompareValue`/`GPIO_L298N_PWM_C0_IDX` 守卫 + EN 置高 + 无编码器脚/无 GPIO 中断断言；`test_syscfg_model.py` 增 L298N/DCC_100_PWM2 同脚区分判例；`test_pin_bindings.py` 纯灰度组测试绑走 l298n EN（PA15）恢复
- [x] 编译验证：`run_l298n_matrix.py` 单选生成 → SysConfig CLI（PWM 实例 TIMG12 + PA14/PB24 + EN PA27 合法性实证）→ gmake 0 error/0 warning；回写 verified=true + notes
