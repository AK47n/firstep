# 模块能力盘点报告

> 只读盘点，数据源：library/modules/*/manifest.json + 模块 .h + stm32 内嵌母版头。

## 1. 平台覆盖与验证状态

| 平台 | 条目数 | verified | unverified | 空 files（内嵌母版） | hardware_bound |
|---|---|---|---|---|---|
| mspm0 | 22 | 1 | 21 | 0 | 5 |
| stm32 | 19 | 7 | 12 | 3 | 1 |

单平台模块（缺对方平台版本）：
- 缺 mspm0（仅 stm32）：debug_uart
- 缺 stm32（仅 mspm0）：huidu, imu_uart, step_motor, xunji

## 2. 模块 × 平台总表

| slug | deps | stm32 files | stm32 verified | stm32 pins | mspm0 files | mspm0 verified | mspm0 pins |
|---|---|---|---|---|---|---|---|---|
| ball_detect | - | 2 | - | 2 | 2 | - | 2 |
| beep | - | 2 | - | 0 | 2 | - | 0 |
| config | - | 1 | - | 8 | 1 | - | 0 |
| debug_uart | config | 2 | - | 2 | - | - | 0 |
| delay | - | 内嵌 | ✓ | 0 | 2 | - | 0 |
| digit_uart | - | 2 | ✓ | 2 | 2 | - | 2 |
| filter | - | 2 | - | 0 | 2 | - | 0 |
| huidu | - | - | - | 0 | 2 | - | 8 |
| imu_uart | delay | - | - | 0 | 2 | - | 2 |
| key | - | 2 | - | 1 | 2 | - | 1 |
| led | - | 内嵌 | ✓ | 0 | 2 | - | 1 |
| led_beep | led, beep, delay | 2 | - | 0 | 2 | - | 0 |
| ml_mpu6050 | - | 2 | ✓ | 2 | 8 | - | 2 |
| motor | - | 2 | ✓ | 10 | 2 | - | 10 |
| ntb_time | - | 2 | - | 0 | 2 | - | 0 |
| oled | delay | 内嵌 | ✓ | 2 | 3 | - | 2 |
| pid | motor | 4 | ✓ | 8 | 4 | ✓ | 8 |
| step_motor | - | - | - | 0 | 2 | - | 5 |
| uart | - | 2 | - | 0 | 2 | - | 0 |
| uwb_uart | config, filter | 2 | - | 2 | 2 | - | 2 |
| xunji | motor | - | - | 0 | 2 | - | 8 |
| zigbee_uart | config | 2 | - | 2 | 2 | - | 2 |
| zigbee_uart_key | config | 2 | - | 2 | 2 | - | 2 |

## 3. 双平台 API 集合差

> stm32 空 files 模块用内嵌母版头补齐（delay→ml_delay.h、led→ml_led.h、oled→ml_oled.h）。
> 名字集合来自函数声明 + 函数式宏（与骨架自检同提取器）。

| slug | stm32 独有 | mspm0 独有 | 共同 |
|---|---|---|---|
| ball_detect | — | — | 4 |
| beep | — | — | 5 |
| delay | delay_s<br>delay_us | — | 1 |
| digit_uart | — | — | 4 |
| filter | — | — | 4 |
| key | — | — | 1 |
| led | LED_GREEN_OFF<br>LED_GREEN_ON<br>LED_RED_OFF<br>LED_RED_ON | — | 4 |
| led_beep | — | — | 4 |
| ml_mpu6050 | MPU6050_GetData<br>MPU6050_Init<br>MPU6050_Read<br>MPU6050_Write | DMP_Init<br>DMP_Read_Data<br>MPU_Read_Len<br>MPU_Write_Len<br>dmp_enable_6x_lp_quat<br>dmp_enable_feature<br>dmp_enable_gyro_cal<br>dmp_enable_lp_quat<br>dmp_get_enabled_features<br>dmp_get_fifo_rate<br>dmp_get_pedometer_step_count<br>dmp_get_pedometer_walk_time<br>dmp_load_motion_driver_firmware<br>dmp_read_fifo<br>dmp_set_accel_bias<br>dmp_set_fifo_rate<br>dmp_set_gyro_bias<br>dmp_set_interrupt_mode<br>dmp_set_orientation<br>dmp_set_pedometer_step_count<br>dmp_set_pedometer_walk_time<br>dmp_set_shake_reject_thresh<br>dmp_set_shake_reject_time<br>dmp_set_shake_reject_timeout<br>dmp_set_tap_axes<br>dmp_set_tap_count<br>dmp_set_tap_thresh<br>dmp_set_tap_time<br>dmp_set_tap_time_multi<br>inv_orientation_matrix_to_scalar<br>inv_row_2_scale<br>mget_ms<br>mpu_configure_fifo<br>mpu_delay_ms<br>mpu_get_accel_fsr<br>mpu_get_accel_reg<br>mpu_get_accel_sens<br>mpu_get_compass_fsr<br>mpu_get_compass_reg<br>mpu_get_compass_sample_rate<br>mpu_get_dmp_state<br>mpu_get_fifo_config<br>mpu_get_gyro_fsr<br>mpu_get_gyro_reg<br>mpu_get_gyro_sens<br>mpu_get_int_status<br>mpu_get_lpf<br>mpu_get_power_state<br>mpu_get_sample_rate<br>mpu_get_temperature<br>mpu_init<br>mpu_init_slave<br>mpu_load_firmware<br>mpu_lp_accel_mode<br>mpu_lp_motion_interrupt<br>mpu_read_fifo<br>mpu_read_fifo_stream<br>mpu_read_mem<br>mpu_read_reg<br>mpu_reg_dump<br>mpu_reset_fifo<br>mpu_run_self_test<br>mpu_set_accel_bias<br>mpu_set_accel_fsr<br>mpu_set_bypass<br>mpu_set_compass_sample_rate<br>mpu_set_dmp_state<br>mpu_set_gyro_fsr<br>mpu_set_int_latched<br>mpu_set_int_level<br>mpu_set_lpf<br>mpu_set_sample_rate<br>mpu_set_sensors<br>mpu_write_mem | 0 |
| motor | encoder_init<br>motorA_duty<br>motorB_duty | limit_duty | 4 |
| ntb_time | — | — | 1 |
| oled | OLED_DrawBMP<br>OLED_SetCursor<br>OLED_ShowBinNum<br>OLED_ShowCharBig<br>OLED_ShowFloat<br>OLED_ShowHexNum<br>OLED_ShowSignedNum<br>OLED_ShowStringBig | I2C_Start<br>I2C_Stop<br>I2C_WaitAck<br>OLED_ClearPoint<br>OLED_ColorTurn<br>OLED_DisPlay_Off<br>OLED_DisPlay_On<br>OLED_DisplayTurn<br>OLED_DrawCircle<br>OLED_DrawLine<br>OLED_DrawPoint<br>OLED_Refresh<br>OLED_ShowChinese<br>OLED_ShowPicture<br>OLED_Test<br>OLED_WR_BP<br>OLED_WR_Byte<br>Send_Byte | 5 |
| pid | — | — | 9 |
| uart | — | — | 3 |
| uwb_uart | — | — | 4 |
| zigbee_uart | — | — | 2 |
| zigbee_uart_key | — | — | 2 |

## 4. 双平台 API 清单

### ball_detect

- stm32：ball_detect_flush, ball_detect_init, ball_detect_parse, ball_detect_rx_handler
- mspm0：ball_detect_flush, ball_detect_init, ball_detect_parse, ball_detect_rx_handler

### beep

- stm32：beep_beep, beep_init, beep_off, beep_on, beep_toggle
- mspm0：beep_beep, beep_init, beep_off, beep_on, beep_toggle

### delay

- stm32：delay_ms, delay_s, delay_us
- mspm0：delay_ms

### digit_uart

- stm32：digit_uart_flush, digit_uart_init, digit_uart_parse, digit_uart_rx_handler
- mspm0：digit_uart_flush, digit_uart_init, digit_uart_parse, digit_uart_rx_handler

### filter

- stm32：filter_add, filter_get, filter_init, filter_reset
- mspm0：filter_add, filter_get, filter_init, filter_reset

### key

- stm32：get_key_state
- mspm0：get_key_state

### led

- stm32：LED_GREEN_OFF, LED_GREEN_ON, LED_RED_OFF, LED_RED_ON, led_init, led_off, led_on, led_toggle
- mspm0：led_init, led_off, led_on, led_toggle

### led_beep

- stm32：led_beep_alarm, led_beep_init, led_beep_off, led_beep_on
- mspm0：led_beep_alarm, led_beep_init, led_beep_off, led_beep_on

### ml_mpu6050

- stm32：MPU6050_GetData, MPU6050_Init, MPU6050_Read, MPU6050_Write
- mspm0：DMP_Init, DMP_Read_Data, MPU_Read_Len, MPU_Write_Len, dmp_enable_6x_lp_quat, dmp_enable_feature, dmp_enable_gyro_cal, dmp_enable_lp_quat, dmp_get_enabled_features, dmp_get_fifo_rate, dmp_get_pedometer_step_count, dmp_get_pedometer_walk_time, dmp_load_motion_driver_firmware, dmp_read_fifo, dmp_set_accel_bias, dmp_set_fifo_rate, dmp_set_gyro_bias, dmp_set_interrupt_mode, dmp_set_orientation, dmp_set_pedometer_step_count, dmp_set_pedometer_walk_time, dmp_set_shake_reject_thresh, dmp_set_shake_reject_time, dmp_set_shake_reject_timeout, dmp_set_tap_axes, dmp_set_tap_count, dmp_set_tap_thresh, dmp_set_tap_time, dmp_set_tap_time_multi, inv_orientation_matrix_to_scalar, inv_row_2_scale, mget_ms, mpu_configure_fifo, mpu_delay_ms, mpu_get_accel_fsr, mpu_get_accel_reg, mpu_get_accel_sens, mpu_get_compass_fsr, mpu_get_compass_reg, mpu_get_compass_sample_rate, mpu_get_dmp_state, mpu_get_fifo_config, mpu_get_gyro_fsr, mpu_get_gyro_reg, mpu_get_gyro_sens, mpu_get_int_status, mpu_get_lpf, mpu_get_power_state, mpu_get_sample_rate, mpu_get_temperature, mpu_init, mpu_init_slave, mpu_load_firmware, mpu_lp_accel_mode, mpu_lp_motion_interrupt, mpu_read_fifo, mpu_read_fifo_stream, mpu_read_mem, mpu_read_reg, mpu_reg_dump, mpu_reset_fifo, mpu_run_self_test, mpu_set_accel_bias, mpu_set_accel_fsr, mpu_set_bypass, mpu_set_compass_sample_rate, mpu_set_dmp_state, mpu_set_gyro_fsr, mpu_set_int_latched, mpu_set_int_level, mpu_set_lpf, mpu_set_sample_rate, mpu_set_sensors, mpu_write_mem

### motor

- stm32：encoder_init, motorA_duty, motorB_duty, motor_encoder_read, motor_init, motor_set_direction, motor_set_duty
- mspm0：limit_duty, motor_encoder_read, motor_init, motor_set_direction, motor_set_duty

### ntb_time

- stm32：get_time_stamp_ms
- mspm0：get_time_stamp_ms

### oled

- stm32：OLED_Clear, OLED_DrawBMP, OLED_Init, OLED_SetCursor, OLED_ShowBinNum, OLED_ShowChar, OLED_ShowCharBig, OLED_ShowFloat, OLED_ShowHexNum, OLED_ShowNum, OLED_ShowSignedNum, OLED_ShowString, OLED_ShowStringBig
- mspm0：I2C_Start, I2C_Stop, I2C_WaitAck, OLED_Clear, OLED_ClearPoint, OLED_ColorTurn, OLED_DisPlay_Off, OLED_DisPlay_On, OLED_DisplayTurn, OLED_DrawCircle, OLED_DrawLine, OLED_DrawPoint, OLED_Init, OLED_Refresh, OLED_ShowChar, OLED_ShowChinese, OLED_ShowNum, OLED_ShowPicture, OLED_ShowString, OLED_Test, OLED_WR_BP, OLED_WR_Byte, Send_Byte

### pid

- stm32：all_white_detect, digtal, gray_init, line_error_calc, line_pid_track, motor_target_set, pid_cal, pid_init, pidout_limit
- mspm0：all_white_detect, digtal, gray_init, line_error_calc, line_pid_track, motor_target_set, pid_cal, pid_init, pidout_limit

### uart

- stm32：UART_send_buffer, UART_send_char, UART_send_string
- mspm0：UART_send_buffer, UART_send_char, UART_send_string

### uwb_uart

- stm32：uwb_filter_reset, uwb_get_frame_rate, uwb_rx_handler, uwb_uart_init
- mspm0：uwb_filter_reset, uwb_get_frame_rate, uwb_rx_handler, uwb_uart_init

### zigbee_uart

- stm32：zigbee_rx_handler, zigbee_uart_init
- mspm0：zigbee_rx_handler, zigbee_uart_init

### zigbee_uart_key

- stm32：zigbee_uart_key_init, zigbee_uart_key_send_id
- mspm0：zigbee_uart_key_init, zigbee_uart_key_send_id



## 5. 双平台 API 差异分类

| slug | 分类 | 说明 |
|---|---|---|
| ball_detect / beep / digit_uart / filter / key / led_beep / ntb_time / pid / uart / uwb_uart / zigbee_uart / zigbee_uart_key | 一致 | 函数集合完全同名（部分全局量语义差异已记录在各自 manifest） |
| motor | 遗留兼容 | stm32 保留 `encoder_init/motorA_duty/motorB_duty`，mspm0 保留 `limit_duty`；统一 API（motor_init/motor_set_direction/motor_set_duty/motor_encoder_read）已是共同 4 个 |
| delay | 真缺口 | mspm0 缺 `delay_us`（`delay_s` 也可补，但需求低） |
| led | 小缺口 | mspm0 缺 stm32 母版侧便捷宏 `LED_RED_ON/OFF`、`LED_GREEN_ON/OFF`（核心函数已一致） |
| oled | 真缺口 | 两侧签名体系不同：stm32 = 行列（Line/Column）定位 + ShowCharBig 等；mspm0 = 像素坐标（x/y）+ size + 绘图函数。共同只有 5 个名字，且共同名的签名也不完全一致 |
| ml_mpu6050 | 有意/待定 | stm32 = 4 个高层 API；mspm0 = 70+ 个 DMP 底层 API。需拍板：mspm0 补 stm32 同款高层封装，还是承认两平台姿态方案不同（mspm0 姿态由 imu_uart 承担） |

## 6. 候选改进优先级（本报告只建议，不实施）

**P0 — 直接影响“打开就能用”**
1. `debug_uart` 补 mspm0：mspm0 冒烟在无 OLED 时没有输出通道（spec 冒烟规则：OLED 为主、debug_uart 为辅）。需先定 UART 实例/引脚（UART0 已给 IMU601，UART1/2/3 已给 DIGIT/UWB/ZIGBEE）。
2. `oled` API 收敛：定一个双平台共同子集与共同签名（建议以“行列定位 + ShowChar/ShowString/ShowNum”为共同层，绘图/旋转/大字体为平台扩展层），否则学生两平台无法写同一份显示代码。
3. 全库编译矩阵：目前 mspm0 只有 `pid` 是 verified，stm32 只有 7 个 verified；其余全部“编译验证未上板/未验证”。建议逐模块逐平台生成最小工程真编译后刷新 verified/notes。

**P1 — 功能拓展类**
4. `delay_us` 补 mspm0（母版 `delay_cycles` 已在，实现极薄）。
5. `ml_mpu6050` mspm0 补 `MPU6050_Init/Read/Write/GetData` 四个高层包装（若姿态不靠 imu_uart 的题）。

**P2 — 一致性小修**
6. `led` mspm0 补 `LED_RED_ON/OFF` 等便捷宏。
7. `motor` manifest notes 明确标注“旧 API = 兼容遗留，新工程请用 motor_* 统一 API”。

**暂缓（已评审）**
- uwb↔filter 可选化：等出现“只要原始 UWB 不要滤波”的真实用例；
- config 解耦：config 是无逻辑参数层，保留；
- 全局结果结构体 getter 化：嵌入式惯例，无痛点前不做。

## 7. 需要用户拍板的问题

1. `debug_uart` mspm0 用哪个 UART 实例/引脚？（与 IMU601 共享 UART0？还是新增固定调试口策略？）
2. `oled` 双平台共同 API 以哪套签名为准？
3. `ml_mpu6050` mspm0 是补高层包装，还是维持“mspm0 姿态走 imu_uart”？
4. 编译矩阵验收口径：先做「编译 0 错」即可，还是连「0 warning」也纳入？（历史基线有 syscfg ovsRate 建议级 warning）

## 8. 盘点边界

- 本报告为只读盘点；未改任何 `library/modules/*`、`library/masters/*`、`src/*`、`tests/*`。
- 数据生成器：`.scratch/module-capability-audit/audit.py`（可重复运行）。