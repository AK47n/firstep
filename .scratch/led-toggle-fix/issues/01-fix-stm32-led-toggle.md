# 01 — stm32 led_toggle 反转逻辑修复

**What to build:** 修 `ml_led.c` 的 `led_toggle`：现在读到高电平又调 `led_on`（保持高）、
读到低电平又调 `led_off`（保持低），等于永不翻转。应改为「高→灭、低→亮」（或直接翻
GPIO）。mspm0 侧 `DL_GPIO_togglePins` 已正确，只改 stm32。

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] `library/masters/stm32/ml_libs/ml_led.c` 的 `led_toggle` 真翻转（高→灭、低→亮）
- [x] stm32 UV4 编译 0 error / 0 warning；mspm0 不动
- [x] pytest 全绿 + mypy src 干净

**Notes:** 源头 = module-multi-instance/03 判据⑤（ml_led 泛型化时发现，HEAD 既有；
行为一致契约下当时未改，另行立项）。修复是行为变化（从「恒不动」到「真翻转」）——
学生代码若曾依赖「toggle 不动」属误用，这是修 bug 而非破坏兼容。
