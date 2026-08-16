# 03 — delay mspm0 补 delay_us

**What to build:** mspm0 delay 模块补 `delay_us(uint32_t us)`，与 stm32 母版 ml_delay 同名同形（基于 CPUCLK_FREQ 换算 delay_cycles）。

**Blocked by:** 无

**Status:** resolved（2026-08-15）

## Comments

- 实现极薄：CPUCLK_FREQ/1e6 × us 调用 delay_cycles；与 stm32 母版 delay_us 同名同形。

- [x] delay.h / delay.c 增 delay_us
- [x] 测试：双平台 delay API 集合含 delay_us
- [x] pytest 全绿 + mypy src 干净
