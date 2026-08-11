# 01 — mspm0 模块缺口补录：pid / digit_uart / filter / gray_track / ball_detect（素材已到位，可实施——编译验证级）

**What to build:** 2026-08-11 MSPM0 线真机验收（2026H 题）发现 mspm0 线模块库只有 9 个（delay/huidu/imu_uart/key/led_beep/motor/ntb_time/oled/uart），H 题实际需要的 pid（摆杆控制）、digit_uart（视觉坐标串口）、filter（滑动滤波）、gray_track（巡线路口检测）、ball_detect（球检）全在库外——推荐只能给库外建议，生成工程里这些功能全是 TODO。stm32 线这些模块都有（21F/26H 提取），mspm0 版需要 DL_xxx driverlib 移植（参照 motor mspm0 先例：`code/motor.c` 用 PWMAB_INST/DC_MOTOR_* 宏 + driverlib API）。

**Status:** open（素材已到位——见下）

## 需求（素材/验证依赖）

1. **移植源**：21F/26H 的 stm32 实现（code/pid.c、digit_uart.c、filter.c、gray_track.c + ball_detect.c/h）→ mspm0 driverlib 移植（DL_Timer/DL_GPIO/DL_UART API + 默认外设布局宏：PID 用 MOTOR_PID_INST + 编码器 IIDX；digit_uart 用 IMU601_INST 同款 UART 或新增 UART 实例）。
2. **验证**：移植后必须能真机编译（syscfg 默认布局已含 MOTOR_PID/NTB/DC_MOTOR 宏，工单 mspm0-syscfg-default 落地后即具备）——"无编译验证的代码不入库"（motor mspm0 悬空代码教训，2026-08-11）。
3. **依赖与自包含**：manifest dependencies 按实际 include 声明（stm32 先例：pid 依赖 motor/gray_track/ml_mpu6050）；`_check_module_self_include` 门禁要求 .c 自含头。
4. **verified 语义**：编译过但未上板 = verified true 或标注"编译验证未上板"（参考 stm32 先例），工单里如实记录。

## 素材到位（2026-08-11 记录，暂缓解除）

- **用户提供完整 TI SDK**：`C:\ti\mspm0_sdk_2_00_01_00\`——149 个官方 driverlib 例程正对 LP_MSPM0G3507（目标器件同型号）+ `source/ti/driverlib/` 全量源码。SDK 不入仓库（5.7GB 级），实施时用绝对路径引用。
- **仓库备份素材**：`sources/materials/MSPM0_MOTOR参考例程/`（7343e80 入库）——MSP_Motor_Ctrl（Modbus 电机控制 + 编码器解析 + CRC16）、m0imu（UART 陀螺仪）、empty.syscfg + ti_msp_dl_config.h/c 真机生成物、移植.md（DL_* API 用法手册）。
- **对照映射**（SDK 例程 → 模块）：
  | 模块 | SDK 参照 |
  |---|---|
  | pid | timg_qei_mode（正交解码）+ timx_timer_mode_pwm_edge_sleep / tima_timer_mode_pwm_dead_band + 库内 motor.c（PWMAB_INST 骨架） |
  | digit_uart | uart_echo_interrupts_standby / uart_rx_multibyte_fifo_dma_interrupts + 移植.md Modbus 解析 |
  | filter | 纯 C，无硬件依赖（stm32 源码直接对照） |
  | gray_track | gpio_input_capture / gpio_simultaneous_interrupts |
  | ball_detect | uart_rx 例程（串口视觉坐标）或 GPIO 输入 |
- **遗留风险（如实记录）**：仍是"编译验证未上板"级——官方例程替代不了实际接线/上板行为验证；移植质量以 DL_* API 用法 + syscfg 宏命名对照官方为准。入库标准 = gmake 编译 0 错（工单 mspm0-syscfg-default 的默认外设布局已落 main c1c9f72，编译验证条件已具备）。

## 验收

- [x] 5 模块 manifest：platforms.mspm0 + files + dependencies 按实际 include 声明，`_check_module_self_include` 门禁过
- [x] 每个模块编译验证：默认外设布局生成工程 gmake 0 错（无编译验证不入库）
- [x] 全量 pytest 绿 + mypy src 干净
- [x] 工单如实记录"编译验证未上板"状态

## 实施记录（2026-08-11，worktree-mspm0-backfill）

- **移植完成**（5 模块全部落地，母版 syscfg 新增 DIGIT_UART = UART1/PA8/PA9，K230 视觉串口）：
  - **pid**：mspm0 = 26H H 题滚球版（pid_mspm0.c/h + gray_track_mspm0.c/h，一圈巡线 + 启停线停车 LAP 状态机 + ball_detect 球坐标解析）。依赖映射：motorA_duty→motor_set_duty(id,duty)；motorA_dir/motorB_dir→motor_set_direction(id,dir)（0停1正转2反转）；Encoder_count1/2→key 模块 counter_1_A/counter_2_A；gz→imu_uart 的 gyro_dps_raw（extern 符号级引用，motor 对 key.c counter 同款先例）；MAX_DUTY=1300（mspm0 PWM 上限，26H 原 50000）。stm32 平台 21F 版不动。
  - **digit_uart**：mspm0 = DIGIT_UART（UART1）RX 中断 + 环形缓冲 + CSV 帧解析（digit_uart_mspm0.c/h），解析逻辑与 21F/26H stm32 版一致。
  - **filter**：纯 C 无平台差异，mspm0 与 stm32 共用同一 filter.c/h（include 从 headfile.h 改为 <stdint.h>，类型等价；26H 源码是卡尔曼版，工单对照表定为滑动滤波，用库内 21F 滑动平均版）。
  - **gray_track**：随 pid 模块补 mspm0（gray_track_mspm0.c/h，26H 版含 start_line_detect 启停线检测；D1-D8 映射母版 HUIDU 宏 L1..R4）。
  - **ball_detect**：新建模块（库内原本没有）——stm32 = 26H 提取（ball_detect_stm32.c/h，USART1 语义）；mspm0 = DL_UART 移植（ball_detect.c/h，DIGIT_UART 实例）。
  - **ml_mpu6050**：补 mspm0 空 files 条目（依赖展开兼容——pid 顶层 dependencies 跨平台共享，stm32 侧 pid.c 真 include ml_mpu6050.h；mspm0 姿态由 imu_uart 承担，无文件复制不参与编译）。
- **编译验证（硬门槛达成）**：复制 out_2026H_mspm0 → build_makefiles.py 扩 12 模块（MODULES 支持多 .c）→ gmake 全量：sysconfig 0 error（DIGIT_UART 宏生成 UART1/PA8/PA9）+ 编译 0 error + 链接出 mspm0_project.out。**未上板**——官方例程替代不了实际接线/上板行为验证（工单素材到位节"遗留风险"原样成立）。
- **门禁**：mspm0 pid 全链（pid/ball_detect/digit_uart/motor/ml_mpu6050）`_check_module_files` + `_check_module_self_include` 过；21F stm32 同链不受影响（ball_detect 有 stm32 条目）。
- **测试**：全量 pytest 1009 绿 + mypy src 干净。
- **10ms 调度说明**：mspm0 pid_control 由 MOTOR_PID_INST_IRQHandler 调用（main.c 先读编码器清零再调 pid_control，26H isr.c TIM3 语义同构）；MOTOR_PID_INST 宏已存在（工单 mspm0-syscfg-default 落地）。
- **遗留**：gray_track 的 D1-D8 ↔ HUIDU 宏映射为编译级默认（物理排列按实际接线调整）；ball_detect/digit_uart 的 UART1_IRQHandler 需用户 main.c 挂载（stm32 线 isr.c 同款结构）。

## 实施提示词（复制到新会话）

```
实施 mspm0 模块缺口补录工单 .scratch/mspm0-modules-backfill/issues/01-backfill.md：
1. 读工单（素材到位节对照表）+ library/modules/motor（mspm0 移植先例：
   manifest platforms 结构 + DL_xxx 宏用法）+ library/modules/pid 等 stm32
   实现（移植源）
2. 素材参照（都本地可读，不入仓库）：
   - 完整 TI SDK：C:\ti\mspm0_sdk_2_00_01_00\examples\nortos\LP_MSPM0G3507\driverlib\<例程>
     （pid→timg_qei_mode + timx_timer_mode_pwm_edge_sleep；digit_uart/ball_detect→
     uart_echo_interrupts_standby / uart_rx_multibyte_fifo_dma_interrupts；
     gray_track→gpio_input_capture / gpio_simultaneous_interrupts）
   - 仓库备份：sources/materials/MSPM0_MOTOR参考例程/（MSP_Motor_Ctrl 编码器解析 +
     m0imu UART 中断 + ti_msp_dl_config.h/c 宏格式 + 移植.md API 用法）
3. 按需求节逐模块移植，manifest 补 platforms.mspm0 + dependencies + files
4. 编译验证（硬门槛）：默认外设布局已落 main（c1c9f72）——重跑 2026H mspm0
   全管线或复制入 .scratch/real-run/out_2026H_mspm0，gmake 0 错才入库；
   工单如实记录"编译验证未上板"
5. 全量 pytest + mypy
6. 提交（data: 前缀，模块库数据）+ 推送
```
