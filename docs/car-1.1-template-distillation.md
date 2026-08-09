# 旧工程提炼：car 1.1（巡线小车模板参考）

> 来源：`C:\Users\luoji\Desktop\car\car 1.1`（真实比赛小车工程，2026-08-09 提炼）
> 性质：参考文档。基于 TI 官方 empty DriverLib 示例改造，CCS **classic 格式**，SDK 2.10.0.04 / sysconfig 1.26.2 / TICLANG 4.0.2.LTS / `__MSPM0G3507__`。

## 一、empty.syscfg：完整外设画像（最有价值）

命名与生成的 `ti_msp_dl_config.h` 宏一一对应，可直接当 syscfg 合成参考。

| 外设 | 实例名 | 关键配置 |
| --- | --- | --- |
| GPIO×8 | GPIO_EncoderA / GPIO_EncoderB（编码器，各 2 pin 中断）| 中断 pin：`interruptEn=true` + `polarity="RISE"` + `interruptPriority="1"` |
| | GPIO_IN（电机 AIN1/AIN2/BIN1/BIN2 方向）| 默认输出 |
| | GPIO_Gray（**敢为 8 路灰度传感器**，模块名）| 8 pin 全 INPUT |
| | GPIO_Key（S1/S2）| INPUT + `internalResistor="PULL_UP"` |
| | GPIO_LED / GPIO_STBY / GPIO_BEEP | LED/STBY 默认；BEEP 带 PULL_UP |
| PWM | PWM_0（TIMG0，PA12/PA13）| `timerCount=2500`，双通道 CC0/CC1 |
| TIMER×2 | TIMER_Encoder_Read（TIMG6）| `timerMode="PERIODIC"`，prescale 256，`timerPeriod="50ms"`，`interrupts=["ZERO"]` |
| | TIMER_0（TIMG7）| 同上，`timerPeriod="10 ms"` |
| UART×2 | UART_0（PA10/PA11，调试）| 115200 |
| | UART_JY61P（PA22/PA23，陀螺仪）| 115200，`enabledInterrupts=["RX"]` |
| I2C | I2C_MPU6050（PB2/PB3）| 备用（代码中未使用）|
| 时钟树 | `SYSCTL.clockTreeEn=true` + PLL | HSCLKMUX→SYSPLL0；PDIV/8、UDIV/2、QDIV×40 → 主频约 80MHz |

syscfg 写作要点：
- GPIO 实例用 `associatedPins.create(N)` + 逐 pin 配置；`$name` 决定宏名（`GPIO_Gray` + `PIN_Gray_1` → `GPIO_Gray_PIN_Gray_1_PORT/PIN`）。
- TIMER/UART 实例名决定代码符号：`TIMER_Encoder_Read` → `TIMER_Encoder_Read_INST`、`TIMER_Encoder_Read_INST_INT_IRQN`；`UART_JY61P` → `UART_JY61P_INST_IRQHandler`。
- 时钟树超频写法：`system.clockTree["PLL_PDIV"].divideValue` 等直接改节点，`SYSCTL.forceDefaultClkConfig = true`。

## 二、代码模块要点

### 敢为 8 路灰度传感器（模块名）
- 8 路 INPUT GPIO，巡线用**加权质心法**：权重 -7..-5..-3..-1..+1..+3..+5..+7，`bias = -(sum/cnt) * gain`。
- gain 调参经验（原工程注释）：直道抖动→减小 gain；弯道跟不住/切外出轨→增大 gain；每次改约 0.5。

### JY61P 串口陀螺仪（= 库中 imu_uart 类模块的真实源）
- 协议：帧头 `0x55 0x53`（角度包），9 字节数据（Roll/Pitch/Yaw/Vel 各 L+H + SUM）。
- 校验：`0x55 + 0x53 + 8 字节数据 == SUM`。
- 角度换算：`(uint16_t)(H<<8 | L) / 32768 * 180`，结果 >180 时减 360。
- 置零命令：`FF AA 69 88 B5`（零漂校准）→ 延时 100ms → `FF AA 01 04 00`（yaw 置零）。
- 接收状态机：WAIT_HEADER1 → WAIT_HEADER2 → RECEIVE_DATA，防丢帧重置。
- 全局 `float Yaw` 供控制模块 `extern` 使用。

### control.c 巡线控制范式
- **增量式 PID**：`Pwm += Kp*(Bias-Last_bias) + Ki*Bias + Kd*(Bias-2*Last_bias+Last2_bias)`；实测 Kp=0.9、Ki=Kd=0（"经测试不需要 I 环和 D 环"）。
- **编码器判向**：双 GPIO 上升沿中断，读另一相电平判正反转（A 相 + B 相）；50ms 定时中断取数，`Current = gEncoderVal / 3` 换算速度。
- **差速转向**：`targetA = Speed_Middle + bias`、`targetB = Speed_Middle - bias`，双轮各跑 PID。
- **方向 + 占空比分离**：`Set_Pwm` 用 AIN1/AIN2 宏控方向，`set_Duty` 改占空比；占空比反向换算 `CompareValue = 2500 - 2500/100*duty`（duty 0~100）。

### Delay
- `delay_cycles(80)` ≈ 1us（主频 80MHz 时）。

## 三、工程结构

- 源文件组织：`empty.c`(main) + `control.c/h` + `Delay.c/h` + `USART_JY61P/JY61P.c/h` —— "巡线小车"赛题的典型模块组合。
- `.cproject` 为 classic 格式（cdtBuildSystem storageModule 直接子元素 + toolChain），与 ccs.py 双格式实现的 classic 侧对应，可作生成结果核对样本。
- 设备/连接：`targetConfigs/MSPM0G3507.ccxml`，XDS110（`TIXDS110_Connection.xml`）。

## 四、对接点

若后续做"智能小车"类赛题模块组合（敢为 8 路灰度 + 双编码器 + 双电机 + JY61P + 按键/LED/BEEP），本页 syscfg 外设表 + 代码范式即完整参考。注意：库中 imu_uart 驱动的是 MSPM0-IMU（新器件，`0A 03 04` 帧 + CRC16），与 JY61P（`0x55 0x53` 帧 + SUM 校验）是**两个不同器件**，各自独立，如需 JY61P 支持需另建模块。
