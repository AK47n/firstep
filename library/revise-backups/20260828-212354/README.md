# 工程说明

## 工程概览

- 平台：TI MSPM0G3507 / CCS
- 开发板：地猛星 MSPM0G3507

## 快速上手：编译 + 烧录

用 TI Code Composer Studio（CCS）打开工程：File → Open Project 选择工程目录
构建：点击 Build（或按 Ctrl+B）生成可烧录固件
下载：接好调试器，点击 Debug（或按 F11）下载到 MSPM0G3507

## 引脚接线表

| 模块 | 角色 | 引脚 | 说明 |
|---|---|---|---|
| motor | PWMAB_C0 | PA12 | pwm（必接） |
| motor | PWMAB_C1 | PA13 | pwm（必接） |
| motor | AIN1 | PB9 | gpio_out（必接） |
| motor | AIN2 | PA18 | gpio_out（必接） |
| motor | BIN1 | PB18 | gpio_out（必接） |
| motor | BIN2 | PA7 | gpio_out（必接） |
| motor | AA | PA16 | enc（必接） |
| motor | AB | PA17 | enc（必接） |
| motor | BA | PB19 | enc（必接） |
| motor | BB | PB20 | enc（必接） |
| xunji | P1 | PA24 | gpio_in（必接） |
| xunji | P2 | PA23 | gpio_in（必接） |
| xunji | P3 | PA22 | gpio_in（必接） |
| xunji | P4 | PA26 | gpio_in（必接） |
| xunji | P5 | PA27 | gpio_in（必接） |
| xunji | P6 | PA25 | gpio_in（必接） |
| xunji | P7 | PB6 | gpio_in（必接） |
| xunji | P8 | PB7 | gpio_in（必接） |
| led | LED | PA15 | gpio_out（必接） |
| led | LED_RED | PA15 | gpio_out |
| ml_mpu6050 | I2C_0_SCL | PA1 | i2c_scl（必接） |
| ml_mpu6050 | I2C_0_SDA | PA0 | i2c_sda（必接） |

> 其余外设引脚以工程内 pin_config.h（stm32）/ mspm0.syscfg 为准

## 模块清单与依赖

- motor：TB6612 双路直流电机驱动（双平台统一 API）：motor_set_duty 调速 + motor_set_direction 方向 + motor_encoder_read 编码器读数（读后清零）。
- xunji：灰度循迹驱动（mspm0）：8 路灰度读取（位图）+ 加权质心巡线核心 + 编码器采样读（读后清零）+ 电机速度输出绑定；适用于巡线/循迹类赛题功能，路口/模式等决策逻辑归生成骨架。（依赖：motor）
- led：LED 指示灯驱动（双平台）：led_init/led_on/led_off/led_toggle + 通道宏 LED_RED/LED_YELLOW/LED_GREEN；拉电流 1=亮 细节已封装在模块内。
- beep：蜂鸣器驱动（双平台）：beep_init/beep_on/beep_off/beep_toggle + beep_beep 响 N 声（阻塞式）。
- delay：MSPM0 毫秒延时：delay_ms 基于 CPUCLK_FREQ 换算调用 delay_cycles，任何时钟频率自动适配。
- led_beep：声光组合模块（双平台）：LED + 蜂鸣器同时开关 + led_beep_alarm 声光报警；只控制一方请选 led 或 beep。（依赖：led、beep、delay）
- ml_mpu6050：MPU6050 六轴传感器的 I2C 通用驱动：提供初始化、寄存器读写以及加速度计和陀螺仪原始数据读取功能，供外部算法进一步解算姿态角；适用于航向保持（车头朝向）、直线行驶纠偏、倾角检测等需要陀螺仪/姿态数据的功能。

## 评分点验收清单

| 编号 | 分区 | 分值 | 原文句子 | 描述 |
|---|---|---|---|---|
| 1 | 基础 | 20 分 | 句子 24 | 完成第（1）项 |
| 2 | 基础 | 20 分 | 句子 28 | 完成第（2）项 |
| 3 | 发挥 | 30 分 | 句子 33 | 完成第（3）项 |
| 4 | 发挥 | 30 分 | 句子 39 | 完成第（4）项 |
| 5 | 未分区 | 20 分 | 句子 40 | 设计报告 |

## 验证顺序清单

按顺序逐个验证，前一个过了再接下一个

- [ ] led — LED 指示灯驱动（双平台）：led_init/led_on/led_off/led_toggle + 通道宏 LED_RED/LED_YELLOW/LED_GREEN；拉电流 1=亮 细节已封装在模块内。
- [ ] delay — MSPM0 毫秒延时：delay_ms 基于 CPUCLK_FREQ 换算调用 delay_cycles，任何时钟频率自动适配。
- [ ] led_beep — 声光组合模块（双平台）：LED + 蜂鸣器同时开关 + led_beep_alarm 声光报警；只控制一方请选 led 或 beep。
- [ ] motor — TB6612 双路直流电机驱动（双平台统一 API）：motor_set_duty 调速 + motor_set_direction 方向 + motor_encoder_read 编码器读数（读后清零）。
- [ ] xunji — 灰度循迹驱动（mspm0）：8 路灰度读取（位图）+ 加权质心巡线核心 + 编码器采样读（读后清零）+ 电机速度输出绑定；适用于巡线/循迹类赛题功能，路口/模式等决策逻辑归生成骨架。
- [ ] beep — 蜂鸣器驱动（双平台）：beep_init/beep_on/beep_off/beep_toggle + beep_beep 响 N 声（阻塞式）。
- [ ] ml_mpu6050 — MPU6050 六轴传感器的 I2C 通用驱动：提供初始化、寄存器读写以及加速度计和陀螺仪原始数据读取功能，供外部算法进一步解算姿态角；适用于航向保持（车头朝向）、直线行驶纠偏、倾角检测等需要陀螺仪/姿态数据的功能。
