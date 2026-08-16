# 03 — ntb_time 补 stm32（get_time_stamp_ms 双平台对偶）

**What to build:** ntb_time 模块补 stm32 版本：`get_time_stamp_ms()` 复用母版 SysTick 1ms 节拍（g_systick），与 mspm0 同名同义；manifest 双平台 + description 统一。

**Blocked by:** 无

**Status:** resolved（2026-08-15）

- [x] ntb_time_stm32.c/h 实现（首次调用 systick_init + 只读 g_systick）
- [x] manifest stm32 条目 + description 双平台统一
- [x] 测试 test_module_ntb_time_stm32.py + pytest 全绿 + mypy 干净
- [x] 真机：stm32/mspm0 冒烟 + 参考路径编译回归 PASS

## Comments

- 已知边界：ml_delay 的 delay_us/delay_ms 是 SysTick 轮询实现，会临时停用 SysTick——delay 期间 g_systick 暂停；需要严格计时的骨架请用 tim_interrupt_ms_init 调度，本时间戳作毫秒级非严格计时（notes 已写）。
