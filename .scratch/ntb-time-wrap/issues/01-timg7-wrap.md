# 01 — ntb_time TIMG7 16 位回绕核实与修复

**What to build:** 工单 mspm0-master-dimx/01 顺带观察（未改）：ntb_time 挂 TIMG7（16 位定时器），40MHz 计数 1.638ms 即回绕，`counter/500` 恒 0——时间戳语义疑似失效。核实 ntb_time.c 的计数用法（Load 值/分频、时间换算公式、回绕处理），定修复方案（换 32 位 TIMG8/TIMG12 实例或软件回绕累加），真机验证。

**Blocked by:** 无

**Status:** 待实施

## 需求

1. 读 `library/modules/ntb_time/code/ntb_time.c` + manifest note：确认 NTB_INST（TIMG7）的计数频率（Load 值/分频）、counter 换算公式、有没有回绕处理。
2. 定方案并实施：换 32 位定时器实例（TIMG8/TIMG12——注意 DCC_100_PWM2 已占 TIMG12）或软件回绕累加；改 syscfg + 代码 + 注释。
3. 验收：gmake 0 错 + 真机（或最小可验证单测）证明时间戳不再 1.638ms 回绕。

## 文件边界

- `library/modules/ntb_time/`（code + manifest）
- `library/masters/mspm0/mspm0.syscfg`（若换实例，实例名 NTB 保留或同步改代码——实例名是模块契约，改哪边同步哪边）

## Comments

- 2026-08-14 立项（mspm0-master-dimx/01 Comments"建议另立工单"）。
