# 01 - 母版 UART 过采样率 3x → 16x

Status: resolved

- `library/masters/mspm0/mspm0.syscfg`：IMU601 / DIGIT_UART / DEBUG_UART /
  UWB_UART / ZIGBEE_UART 五个实例 `ovsRate` `"3"` → `"16"`（全 BUSCLK +
  115200，同构）。
- 桌面 2024H_Auto_Car 同步改 + SysConfig CLI 重生成 + gmake -B 全量
  exit=0（实际波特率 115211.52，+0.010%）。
- 母版回归：真实生成新工程 gmake 全量 0 警告 0 错误（基线警告消失）。
- references/ 两个 LFCLK 示例不动（低时钟 OSR 受限，保留原样）。
