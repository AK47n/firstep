# 02 — pca9685 模块（16 路舵机驱动板，手册 control--16-ch-servo-drive-module.md）

**要做什么：** 模块库新增 `pca9685` 条目（仅 mspm0）：软 I2C 位操作（2 GPIO，照 AHT10 先例不占硬件 I2C 外设）驱动 PCA9685 16 路 PWM 寄存器——`pca9685_init(freq_hz)`（MODE1 复位 + 频率 prescale + 16 路归零）+ `pca9685_set_pwm(ch, width)`（12bit 计数，ON=0）+ `pca9685_set_angle(ch, angle)`（0-180° ↔ 0.5-2.5ms，**与库内 servo 模块同一口径**）+ `pca9685_set_freq` + `pca9685_set_address`（A5..A0，0x40-0x7F）；选中后生成工程打开即可编译。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论：** 2026-09-05 完成并提交。软 I2C 位操作原语照 aht10 先例（SCL 半周期 2-4us、SDA 方向运行时切换，宏 `<实例>_<引脚>_PIN/_IOMUX`）；驱动核心 = 12bit 计数（0-4095）ON=0/OFF=width、prescale = round(25e6/4096/freq)-1（睡眠→写→唤醒→恢复 MODE1|0xA1 保页面行为）、地址 (0x40+A5)<<1 可级联 62 板；set_angle 按当前频率把 0.5-2.5ms 换算成计数（50Hz 下 102.4-512 tick），**与 servo 模块（TIMG8 硬件 PWM 单路）同口径互补**：单路舵机用 servo、多路/机械臂用 pca9685——manifest notes 写清区别；母版 syscfg 新 GPIO 实例 PCA9685（SCL 输出 / SDA 输出初始 CLEARED——运行时切换），默认 SCL=PB6/SDA=PB7（与 STEP_MOTOR SLP2/DIR2、HUIDU R3/R4、AHT10 SCL/SDA、DHT11 DATA 重叠——16 路舵机执行与温湿度/步进/巡线同选概率最低，同选经引脚绑定消解）；不占 TIMER（PWM 由芯片内部 25MHz 振荡器生成）/不占硬件 I2C 外设。单选生成 → gmake 0 error / 0 warning（PASS）；未上板。**code-review 收尾修正**：set_angle 计点整数截断改浮点（0° 曾落 0.49ms 边）；prescale 整数先除截断改浮点 round（frac≥0.5 时曾差 1——60Hz 应 101 得 100）；测试增源码守卫（test_pca9685_prescale_round_guard）。

- [ ] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/control--16-ch-servo-drive-module.md` 「代码块」章节抽完整 `bsp_pca9685.c/h` → 改造为 `code/pca9685.c` + `code/pca9685.h`：去 main/printf、函数名规范化（`pca9685_init/set_pwm/set_angle/set_freq/set_address`，去掉页内 `IIC_Start`/`Send_Byte`/`PCA9685_setPWM` 菜市场命名收敛为静态原语 + 规范服务函数）、`delay_1ms` → `delay_ms`（delay 模块）、页面 FLOOR Excel 注释剔除、SDA_OUT/IN 宏照 AHT10 先例（`DL_GPIO_initDigitalOutput/Input` + `enableOutput`）
- [ ] 角度映射：0-180° ↔ 0.5-2.5ms（50Hz/20ms 标准舵机时基——**与 servo 模块同口径**：servo_duty_for_angle 同款 0.5-2.5ms 线性映射）；按当前频率换算计数（min = 4096*0.0005*freq、max = 4096*0.0025*freq，默认 50Hz）；set_pwm 与 set_angle 分离（set_w pwm 任意脉宽、占空比 0-100% 由调用方换算）
- [ ] 母版 `mspm0.syscfg`：新 GPIO 实例 `PCA9685`（2 associatedPins：SCL OUTPUT / SDA OUTPUT initialValue CLEARED——运行时切换，照 AHT10_SDA 先例）；默认脚 = SCL PB6 / SDA PB7（与 STEP_MOTOR SLP2/DIR2、HUIDU R3/R4、AHT10 SDA/SCL、DHT11 DATA 重叠——多路舵机执行与温湿度采集/步进（互替）/巡线同选概率最低，同选时经引脚绑定消解）；软 I2C 需板上/模块自带上拉（AHT10 先例）
- [ ] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"PCA9685": ("pca9685",)`
- [ ] `manifest.json`：`dependencies: ["delay"]`（软 I2C 位操作延时）；mspm0 平台条目（files/verified 初 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接+改造要点+编译记录+**与 servo 模块区分说明**——servo = TIMG8 硬件 PWM 单路（50Hz 周期主控定时器生成）、pca9685 = 16 路 I2C 寄存器扩展（芯片内部振荡器生成），二者 API 都出 0.5-2.5ms 角度语义、互补不重复）；pins：SCL/SDA = gpio_out（default 按分配）；简介判据：能力方向（多舵机控制/机械臂/多路 PWM 输出）+ 无题绑定
- [ ] wordlist.json 补录：「执行机构」加「PCA9685 16 路舵机驱动板」方案挂 `lib_modules: ["pca9685"]`；models 加 "PCA9685"
- [ ] 测试：`test_pins.py::MSPM0_DEFAULT_MAP` 增 2 对；`test_syscfg_prune.py` 增 PCA9685 断言；`test_pin_bindings.py` 刻意表（PB6 3→4、PB7 4→5 + 注释）；新增 `tests/test_module_pca9685.py`（manifest 结构 + 单选生成 → syscfg 含 PCA9685 + 文件落盘 + main.c 调 init/set_angle 过静态门禁）
- [ ] 编译验证：复制 `run_joystick_matrix.py` 改 slug 为 pca9685（main.c 调 init+set_angle+set_pwm）→ gmake 真编译 0 error、模块自身 warning 0（`C:/ti/ccs2050`）；结果回写 manifest verified=true + notes 记录；code-review 后中文提交
