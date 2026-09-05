# 06 — sr04 模块（超声波测距，手册 sensor--sr04-ultrasonic-ranging-sensor.md）

**要做什么：** 模块库新增 `sr04` 条目（仅 mspm0）：从手册代码块提炼完整驱动为纯驱动切片（TRIG 触发 + ECHO 脉冲计时 + 距离换算 cm，1ms 定时器中断计数保留——测距必需），选中后生成即编译、可调用（`sr04_init()` + `sr04_get_distance_cm()` 类服务函数）——超声波测距/避障类赛题无需自备驱动。

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

- [ ] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--sr04-ultrasonic-ranging-sensor.md`「代码块」章节抽 `bsp_ultrasonic.c/h` 全文 → 模块规范改写（`code/sr04.c/h`；TRIG/ECHO 引脚宏参数化；定时器中断计数照 ntb_time `NTB_INST_IRQHandler` 先例；delay_us/delay_ms 走 delay 依赖；去掉 main.c 演示/printf；5 次测量均值等按手册算法保留为纯函数）
- [ ] 母版 `mspm0.syscfg` 加：GPIO 输出实例（TRIG）+ GPIO 输入实例（ECHO）+ TIMER 实例（Basic_Periodic 1ms 中断，闲置 TIMGx——不占用 MOTOR_PID/NTB/SERVO_PWM 的 TIM 外设，计时基准 = 时钟 1MHz 换 1us 分辨率，按手册 800kHz 说明核对）；`syscfg_instances.py` 登记（TIMER 实例 → sr04 slug）
- [ ] `manifest.json`：`dependencies: ["delay"]`；mspm0 平台条目（kit/source_url = 手册原页；notes 含手册路径 + 原页 + 网盘链接 + 改造要点 + 定时器实例说明）；简介能力方向（超声波测距 / 避障 / 液位高度辅助测量）+ 无题绑定；pins 1 × gpio_out(TRIG) + 1 × gpio_in(ECHO)
- [ ] wordlist.json 补录：「感知传感器」类加「HC-SR04 超声波测距」方案挂 `lib_modules: ["sr04"]`
- [ ] 测试：`test_pins.py::MSPM0_DEFAULT_MAP` 增映射；`test_syscfg_prune.py` 增实例保留/裁剪断言；新增 `tests/test_module_sr04.py`（单选生成 → syscfg 含实例 + 文件落盘 + main.c 调 init/测距过静态门禁）
- [ ] 定时器实例冲突核查：sr04 所选 TIM 外设与骨架调度/滴答/PWM 绑定无冲突（照 TIM 门禁口径自查，默认组合不拦）
- [ ] 编译验证：gmake 真编译 0 error、模块 warning 0；回写 manifest verified/notes
