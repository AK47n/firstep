# 工单：mspm0-uart-osr（母版 UART 过采样率基线清理）

## 背景

生成工程 SysConfig 长期带一条基线警告：

`IMU601(/ti/driverlib/UART) ovsRate: A higher oversampling rate is possible
given the target baud rate and UART clock source frequency. It is recommended
to pick a higher oversampling rate to improve tolerance to clock deviation.`

根源：`library/masters/mspm0/mspm0.syscfg` 把 5 个 UART 实例（IMU601 /
DIGIT_UART / DEBUG_UART / UWB_UART / ZIGBEE_UART）的 `ovsRate` 全部写死
`"3"`（几乎最低档，每 bit 只采样 3 次，抗时钟偏差能力弱）。各 manifest
notes 多处记录「syscfg ovsRate 基线 warning（非模块代码）」——已知噪音。

## 决策

- 全实例同构（`uartClkSrc = "BUSCLK"`、`targetBaudRate = 115200`、默认
  32MHz 时钟）——同一 (时钟, 波特率) 组合，`ovsRate = "16"` 一处验证可行
  则全部可行。
- 真机验证（IMU601，桌面工程）：16x 时实际波特率 115211.52
  （+0.010%，远优于 ±2% 容差），SysConfig 无 warning、全量编译 0 错。
- 仅改母版 BUSCLK/115200 的 5 处；`library/references/` 下两个示例用
  LFCLK（32.768kHz）场景，OSR=3 是低时钟下的选择，**不动**。
- references 里的示例 targetBaudRate 9600（UART-回显-中断-待机），
  LFCLK 下 OSR 受限，保持原样。

## 验证

- 桌面 2024H_Auto_Car：改 syscfg → SysConfig CLI 重生成 → gmake -B 全量
  exit=0，`2024H_Auto_Car.out` 重新产出。
- 母版回归：真实生成新工程 → syscfg `ovsRate = "16"` → gmake 全量
  exit=0、**0 警告 0 错误**（基线警告消失）、`mspm0_project.out` 产出。

## 影响

对用户：编译输出少一条告警；IMU 串口抗时钟偏差/噪声能力升到 16x。
对领域：后续所有 mspm0 生成工程不再带 ovsRate 基线警告。
