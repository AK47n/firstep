# 01 — mspm0 模块缺口补录：pid / digit_uart / filter / gray_track / ball_detect（素材已到位，可实施——编译验证级）

**What to build:** 2026-08-11 MSPM0 线真机验收（2026H 题）发现 mspm0 线模块库只有 9 个（delay/huidu/imu_uart/key/led_beep/motor/ntb_time/oled/uart），H 题实际需要的 pid（摆杆控制）、digit_uart（视觉坐标串口）、filter（滑动滤波）、gray_track（巡线路口检测）、ball_detect（球检）全在库外——推荐只能给库外建议，生成工程里这些功能全是 TODO。stm32 线这些模块都有（21F/26H 提取），mspm0 版需要 DL_xxx driverlib 移植（参照 motor mspm0 先例：`code/motor.c` 用 PWMAB_INST/DC_MOTOR_* 宏 + driverlib API）。

**Status:** open（素材已到位——见下）

## 需求（素材/验证依赖）

1. **移植源（2026-08-11 领域建模修订：原生平台真机代码优先，见 CONTEXT.md「入库路径」）**：**首选原生 mspm0 真机工程 `sources/car/car xunji`**（Debug/PWM.out 真机编译产物在，与 car 1.1 同源、已归档为 car-1-1-巡线模板-mspm0 参考）——gray_track（巡线路口）的 mspm0 版源 = control.c 的白色区域计数路口检测 + xunji_template 加权质心 + AB/ABCDA/ACBDA 模式状态机，直接适配默认外设布局宏即可（GPIO_Gray_* 8 路 → HUIDU_L3/L2/L1/R1/R2/L4/R3/R4，对照 huidu/motor manifest 宏名；DC_MOTOR/编码器/定时器同理）；**21F/26H 的 stm32 实现（code/pid.c、digit_uart.c、filter.c、gray_track.c + ball_detect.c/h）降级为对照参考**（仅当原生源缺能力时才用，且走 DL_Timer/DL_GPIO/DL_UART driverlib 移植：PID 用 MOTOR_PID_INST + 编码器 IIDX；digit_uart 用 IMU601_INST 同款 UART 或新增 UART 实例）。
2. **验证**：移植后必须能真机编译（syscfg 默认布局已含 MOTOR_PID/NTB/DC_MOTOR/HUIDU 宏，工单 mspm0-syscfg-default 落地后即具备）——"无编译验证的代码不入库"（motor mspm0 悬空代码教训，2026-08-11）。
3. **依赖与自包含**：manifest dependencies 按实际 include 声明（stm32 先例：pid 依赖 motor/gray_track/ml_mpu6050）；`_check_module_self_include` 门禁要求 .c 自含头。
4. **verified 语义**：编译过但未上板 = verified true 或标注"编译验证未上板"（参考 stm32 先例），工单里如实记录。
5. **巡线题专用层命名**：car xunji 补录的巡线套装模块建议按先例标注"2024H 巡线题专用"（对偶 stm32 pid 的"2021F 巡线题专用"）；注意 car xunji 陀螺仪为 JY61P（USART_JY61P），与库内 imu_uart（IMU601 UART0）不同件，补录时按需取舍并如实标注硬件绑定。

## 素材到位（2026-08-11 记录，暂缓解除）

- **用户提供完整 TI SDK**：`C:\ti\mspm0_sdk_2_00_01_00\`——149 个官方 driverlib 例程正对 LP_MSPM0G3507（目标器件同型号）+ `source/ti/driverlib/` 全量源码。SDK 不入仓库（5.7GB 级），实施时用绝对路径引用。
- **仓库备份素材**：`sources/materials/MSPM0_MOTOR参考例程/`（7343e80 入库）——MSP_Motor_Ctrl（Modbus 电机控制 + 编码器解析 + CRC16）、m0imu（UART 陀螺仪）、empty.syscfg + ti_msp_dl_config.h/c 真机生成物、移植.md（DL_* API 用法手册）。
- **对照映射**（2026-08-11 修订：原生优先，SDK/官方例程降级为对照）：
  | 模块 | 首选移植源（原生 mspm0 真机） | 对照参考 |
  |---|---|---|
  | pid（摆杆） | （无原生源，走移植） | timg_qei_mode（正交解码）+ timx_timer_mode_pwm_edge_sleep / tima_timer_mode_pwm_dead_band + 库内 motor.c（PWMAB_INST 骨架） |
  | digit_uart | （无原生源，走移植） | uart_echo_interrupts_standby / uart_rx_multibyte_fifo_dma_interrupts + 移植.md Modbus 解析 |
  | filter | 纯 C，无硬件依赖（stm32 源码直接对照） | — |
  | gray_track（巡线路口） | **car xunji control.c 白色区域计数 + xunji_template 加权质心 + AB/ABCDA/ACBDA 状态机**（GPIO_Gray_* → HUIDU_* 宏适配） | gpio_input_capture / gpio_simultaneous_interrupts |
  | ball_detect | （无原生源，走移植） | uart_rx 例程（串口视觉坐标）或 GPIO 输入 |
- **遗留风险（如实记录）**：仍是"编译验证未上板"级——官方例程替代不了实际接线/上板行为验证；移植质量以 DL_* API 用法 + syscfg 宏命名对照官方为准。入库标准 = gmake 编译 0 错（工单 mspm0-syscfg-default 的默认外设布局已落 main c1c9f72，编译验证条件已具备）。

## 验收

- [ ] 5 模块 manifest：platforms.mspm0 + files + dependencies 按实际 include 声明，`_check_module_self_include` 门禁过
- [ ] 每个模块编译验证：默认外设布局生成工程 gmake 0 错（无编译验证不入库）
- [ ] 全量 pytest 绿 + mypy src 干净
- [ ] 工单如实记录"编译验证未上板"状态

## 实施提示词（复制到新会话）

```
实施 mspm0 模块缺口补录工单 .scratch/mspm0-modules-backfill/issues/01-backfill.md：
1. 读工单（需求节 1 移植源修订 + 对照映射表）+ CONTEXT.md「入库路径」词条
   （补录移植源判据：原生平台真机代码优先）+ library/modules/motor（mspm0
   先例：manifest platforms 结构 + DL_xxx 宏用法）+ library/modules/pid 等
   stm32 实现（对照参考）
2. 素材参照（都本地可读）：
   - 首选原生源：sources/car/car xunji（mspm0 真机工程，Debug/PWM.out 在）——
     gray_track 巡线路口/巡线套装 = control.c（白区计数路口 + AB/ABCDA/ACBDA
     状态机 + 声光）+ xunji_template.c（加权质心核心），GPIO_Gray_* 8 路宏 →
     默认布局 HUIDU_L3/L2/L1/R1/R2/L4/R3/R4 适配（对照 huidu/motor manifest）
   - 已归档副本：library/references/car-1-1-巡线模板-mspm0/（同源 + 规格文档
     xunji_logic_spec.md）
   - 完整 TI SDK：C:\ti\mspm0_sdk_2_00_01_00\examples\nortos\LP_MSPM0G3507\driverlib\<例程>
     （仅 pid/digit_uart/ball_detect 无原生源的走移植：pid→timg_qei_mode +
     timx_timer_mode_pwm_edge_sleep；digit_uart/ball_detect→
     uart_echo_interrupts_standby / uart_rx_multibyte_fifo_dma_interrupts）
   - 仓库备份：sources/materials/MSPM0_MOTOR参考例程/（MSP_Motor_Ctrl 编码器解析 +
     m0imu UART 中断 + ti_msp_dl_config.h/c 宏格式 + 移植.md API 用法）
3. 按需求节逐模块补录，manifest 补 platforms.mspm0 + dependencies + files；
   巡线套装模块标注"2024H 巡线题专用"（对偶 pid 的"2021F 巡线题专用"）
4. 编译验证（硬门槛）：默认外设布局已落 main（c1c9f72）——重跑 2026H mspm0
   全管线或复制入 .scratch/real-run/out_2026H_mspm0，gmake 0 错才入库；
   工单如实记录"编译验证未上板"
5. 全量 pytest + mypy
6. 提交（data: 前缀，模块库数据）+ 推送
```
