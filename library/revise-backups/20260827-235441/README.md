# 工程说明

## 工程概览

- 平台：STM32F103C8T6 / Keil5
- 开发板：STM32F103C8T6 最小系统板（蓝药丸）

## 快速上手：编译 + 烧录

用 Keil MDK（uVision5）打开工程：双击 user/Project.uvprojx
编译：点击 Build（Project → Build Target，或按 F7）生成可烧录固件
烧录：接好 ST-Link，点击 Download（或按 F8）下载到 STM32F103C8T6

## 引脚接线表

| 模块 | 角色 | 引脚 | 说明 |
|---|---|---|---|
| oled | OLED_SCL | PB8 | i2c_scl（必接） |
| oled | OLED_SDA | PB9 | i2c_sda（必接） |
| key | KEY_START | PB3 | gpio_in（必接） |
| motor | MOTOR_A_PWM | PA0 | pwm（必接） |
| motor | MOTOR_A_DIR | PA6 | gpio_out（必接） |
| motor | MOTOR_A_DIR2 | PA7 | gpio_out（必接） |
| motor | MOTOR_B_PWM | PA1 | pwm（必接） |
| motor | MOTOR_B_DIR | PB0 | gpio_out（必接） |
| motor | MOTOR_B_DIR2 | PB1 | gpio_out（必接） |
| motor | MOTOR_A_ENC | PB5 | enc（必接） |
| motor | MOTOR_A_ENC_DIR | PB4 | gpio_in（必接） |
| motor | MOTOR_B_ENC | PA4 | enc（必接） |
| motor | MOTOR_B_ENC_DIR | PA5 | gpio_in（必接） |

> 其余外设引脚以工程内 pin_config.h（stm32）/ mspm0.syscfg 为准

## 模块清单与依赖

- led：LED 指示灯驱动（双平台）：led_init/led_on/led_off/led_toggle + 通道宏 LED_RED/LED_YELLOW/LED_GREEN；拉电流 1=亮 细节已封装在模块内。
- beep：蜂鸣器驱动（双平台）：beep_init/beep_on/beep_off/beep_toggle + beep_beep 响 N 声（阻塞式）。
- delay：MSPM0 毫秒延时：delay_ms 基于 CPUCLK_FREQ 换算调用 delay_cycles，任何时钟频率自动适配。
- oled：0.96 寸 OLED（SSD1306）I2C 显示驱动：硬件 I2C 显存式绘图（画点/字符/字符串/汉字，支持反色与 180° 旋转），带 16×8 ASCII 字库。（依赖：delay）
- key：按键读取（双平台）：get_key_state 读取按键（上拉低电平按下）；stm32 默认 PB3（JTDO 复位后可用），mspm0 默认 PA2。
- motor：TB6612 双路直流电机驱动（双平台统一 API）：motor_set_duty 调速 + motor_set_direction 方向 + motor_encoder_read 编码器读数（读后清零）。
- ntb_time：系统毫秒时间戳（双平台统一 get_time_stamp_ms）：mspm0 用 NTB 定时器回绕累加，stm32 用 SysTick 1ms 节拍。

## 评分点验收清单

| 编号 | 分区 | 分值 | 原文句子 | 描述 |
|---|---|---|---|---|
| s1 | 基础 | 20 分 | 未关联原文 | 循迹送药 |

## 验证顺序清单

按顺序逐个验证，前一个过了再接下一个

- [ ] led — LED 指示灯驱动（双平台）：led_init/led_on/led_off/led_toggle + 通道宏 LED_RED/LED_YELLOW/LED_GREEN；拉电流 1=亮 细节已封装在模块内。
- [ ] delay — MSPM0 毫秒延时：delay_ms 基于 CPUCLK_FREQ 换算调用 delay_cycles，任何时钟频率自动适配。
- [ ] beep — 蜂鸣器驱动（双平台）：beep_init/beep_on/beep_off/beep_toggle + beep_beep 响 N 声（阻塞式）。
- [ ] oled — 0.96 寸 OLED（SSD1306）I2C 显示驱动：硬件 I2C 显存式绘图（画点/字符/字符串/汉字，支持反色与 180° 旋转），带 16×8 ASCII 字库。
- [ ] key — 按键读取（双平台）：get_key_state 读取按键（上拉低电平按下）；stm32 默认 PB3（JTDO 复位后可用），mspm0 默认 PA2。
- [ ] motor — TB6612 双路直流电机驱动（双平台统一 API）：motor_set_duty 调速 + motor_set_direction 方向 + motor_encoder_read 编码器读数（读后清零）。
- [ ] ntb_time — 系统毫秒时间戳（双平台统一 get_time_stamp_ms）：mspm0 用 NTB 定时器回绕累加，stm32 用 SysTick 1ms 节拍。
