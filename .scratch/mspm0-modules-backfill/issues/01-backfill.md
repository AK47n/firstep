# 01 — mspm0 模块缺口补录：pid / digit_uart / filter / gray_track / ball_detect（暂缓，素材依赖）

**What to build:** 2026-08-11 MSPM0 线真机验收（2026H 题）发现 mspm0 线模块库只有 9 个（delay/huidu/imu_uart/key/led_beep/motor/ntb_time/oled/uart），H 题实际需要的 pid（摆杆控制）、digit_uart（视觉坐标串口）、filter（滑动滤波）、gray_track（巡线路口检测）、ball_detect（球检）全在库外——推荐只能给库外建议，生成工程里这些功能全是 TODO。stm32 线这些模块都有（21F/26H 提取），mspm0 版需要 DL_xxx driverlib 移植（参照 motor mspm0 先例：`code/motor.c` 用 PWMAB_INST/DC_MOTOR_* 宏 + driverlib API）。

**Status:** open（暂缓——见下）

## 需求（素材/验证依赖）

1. **移植源**：21F/26H 的 stm32 实现（code/pid.c、digit_uart.c、filter.c、gray_track.c + ball_detect.c/h）→ mspm0 driverlib 移植（DL_Timer/DL_GPIO/DL_UART API + 默认外设布局宏：PID 用 MOTOR_PID_INST + 编码器 IIDX；digit_uart 用 IMU601_INST 同款 UART 或新增 UART 实例）。
2. **验证**：移植后必须能真机编译（syscfg 默认布局已含 MOTOR_PID/NTB/DC_MOTOR 宏，工单 mspm0-syscfg-default 落地后即具备）——"无编译验证的代码不入库"（motor mspm0 悬空代码教训，2026-08-11）。
3. **依赖与自包含**：manifest dependencies 按实际 include 声明（stm32 先例：pid 依赖 motor/gray_track/ml_mpu6050）；`_check_module_self_include` 门禁要求 .c 自含头。
4. **verified 语义**：编译过但未上板 = verified true 或标注"编译验证未上板"（参考 stm32 先例），工单里如实记录。

## 暂缓原因（2026-08-11 记录）

- 移植是无真实 mspm0 硬件素材的"纸面移植"——26H/21F 是 stm32 工程，没有 mspm0 的真实电机/传感工程可对照（库里 mspm0 motor.c 的宏名只能从 notes 推）。
- 移植质量只能证编译、不能证行为。**等用户提供真实 mspm0 工程（逐飞 MSPM0 小车 / 自己的带外设 syscfg 工程）或明确要求纸面移植**再实施。
- 触发条件：用户提供 mspm0 真实工程素材，或点选"纸面移植（编译验证）"。

## 实施提示词（触发后使用）

```
实施 mspm0 模块缺口补录工单 .scratch/mspm0-modules-backfill/issues/01-backfill.md：
1. 读工单 + library/modules/motor（mspm0 移植先例：manifest platforms 结构 +
   DL_xxx 宏用法）+ library/modules/pid 的 stm32 实现（移植源）
2. 按需求节逐模块移植（pid/digit_uart/filter/gray_track/ball_detect），
   manifest 补 platforms.mspm0 + dependencies + files
3. 每个模块用默认外设布局编译验证（复制到 .scratch/real-run/out_2026H_mspm0
   或重生成，gmake 0 错）——无编译验证不入库
4. 全量 pytest + mypy
5. 提交（data: 前缀，模块库数据）+ 推送
```
