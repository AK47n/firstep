# 01 — ntb_time TIMG7 16 位回绕核实与修复

**What to build:** 工单 mspm0-master-dimx/01 顺带观察（未改）：ntb_time 挂 TIMG7（16 位定时器），40MHz 计数 1.638ms 即回绕，`counter/500` 恒 0——时间戳语义疑似失效。核实 ntb_time.c 的计数用法（Load 值/分频、时间换算公式、回绕处理），定修复方案（换 32 位 TIMG8/TIMG12 实例或软件回绕累加），真机验证。

**Blocked by:** 无

**Status:** resolved（2026-08-15 PR #83 squash merged ee6225f，主会话复核 + 1538 绿复跑）

## 需求

1. 读 `library/modules/ntb_time/code/ntb_time.c` + manifest note：确认 NTB_INST（TIMG7）的计数频率（Load 值/分频）、counter 换算公式、有没有回绕处理。
2. 定方案并实施：换 32 位定时器实例（TIMG8/TIMG12——注意 DCC_100_PWM2 已占 TIMG12）或软件回绕累加；改 syscfg + 代码 + 注释。
3. 验收：gmake 0 错 + 真机（或最小可验证单测）证明时间戳不再 1.638ms 回绕。

## 文件边界

- `library/modules/ntb_time/`（code + manifest）
- `library/masters/mspm0/mspm0.syscfg`（若换实例，实例名 NTB 保留或同步改代码——实例名是模块契约，改哪边同步哪边）

## 实施记录（2026-08-15，worktree ntb-time-wrap-01）

- **核实结论**（比工单观察更严重）：母版 NTB = TIMG7 Basic_Periodic，SysConfig
  默认生成 32MHz/256=125kHz、period=62499+1=62500 ticks=**500ms/周**（不是
  1.638ms——dimx 母版已带 prescale）。旧 `ntb_time.c` 三个问题叠加：① 从未
  `startCounter`，计数器不跑，`get_time_stamp_ms` 恒 0；② `counter/500`
  即使跑起来也不是毫秒（125kHz 下应 /125）；③ 计数器为 LOAD 向下数，
  已走时间 = LOAD - 当前计数值。
- **方案**：软件回绕累加（零 syscfg 改动，TIMG7 16 位在 62500 周期下够用，
  且默认产物逐字节契约不破）。`NTB_INST_IRQHandler` 在 ZERO 中断 +500ms；
  `get_time_stamp_ms` 首次调用自启动计数器并开 NVIC，返回
  `g_ntb_ms + (LOAD - remaining) * 500 / (LOAD + 1)`。
- **文件改动**：`library/modules/ntb_time/code/ntb_time.c`（重写实现）+
  `manifest.json` note 同步；syscfg 零改动。
- **验收**：pytest 1538 passed + mypy src 41 文件干净；真机 2024H 十模块
  默认生成 gmake 0 错 0 警 + ntb_time.o 在产物（证据
  .scratch/real-run/ntb_realrun.log）。运行级（跨 500ms 周的时间戳连续性）
  用户上板自验：`get_time_stamp_ms()` 差值应随真实毫秒线性增长。

## Comments

- 2026-08-14 立项（mspm0-master-dimx/01 Comments"建议另立工单"）。
- **合并复核**（PR #83 squash merged ee6225f，主会话）：核实结论成立——dimx
  母版 NTB 已由 SysConfig 生成 125kHz/500ms 周期，旧实现确实未 startCounter
  且 /500 不是毫秒、未处理 LOAD 向下数；软件回绕累加方案零 syscfg 改动、
  默认逐字节契约不破；NTB_INST_IRQHandler 与 get_time_stamp_ms 实现正确
  （ZERO 中断 +500ms；LOAD-remaining 拼周内毫秒；首次调用自启动 + NVIC）。
  合并后 main 复跑 1538 绿 + mypy 41 文件干净。worktree ntb-time-wrap-01
  照例保留。
