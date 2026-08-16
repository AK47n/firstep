# 05 — P2 收尾：led 便捷宏 + motor 旧 API 标注

**What to build:** led mspm0 补 `LED_RED_ON/OFF`、`LED_YELLOW_ON/OFF`、`LED_GREEN_ON/OFF` 便捷宏（stm32 母版补黄色宏，两侧对齐）；motor manifest notes 明确旧 API 为兼容遗留、新工程请用 motor_* 统一 API。随后把模块能力盘点报告 P2 项标为已完成。

**Blocked by:** 04


## Comments

- 黄色宏补齐是顺手对齐：原 stm32 只有红/绿，现双平台三色 ON/OFF 齐全。
- 能力盘点报告 P2 已全部勾销；后续剩余只有明确缓议项（uwb↔filter 可选化等）。
**Status:** resolved（2026-08-15）

- [x] mspm0 led.h 三色 ON/OFF 宏；stm32 ml_led.h 补黄色 ON/OFF
- [x] motor 双平台 notes 标注旧 API 兼容遗留
- [x] 测试：两平台 led 宏集合一致
- [x] pytest 全绿 + mypy src 干净
