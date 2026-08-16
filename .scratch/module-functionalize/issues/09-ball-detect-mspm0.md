# 09 — ball_detect 补 mspm0（已有实现核对 + 声明补全）

**What to build:** ball_detect 已有 mspm0 实现（DIGIT_UART/UART1 共享、PA8/PA9）核对通过并补全声明：manifest mspm0 条目补 pins（BALL_DETECT_UART_TX/RX）；与 digit_uart 同选时 main.c 单个 UART1_IRQHandler 聚合两个 rx_handler；真机 gmake 0 错留痕。

**Blocked by:** 08

**Status:** resolved（2026-08-15）

- [x] 核对 ball_detect.c/h：include 自含、DL_UART 宏消费、init/flush/rx_handler/parse API 与 stm32 版同形
- [x] manifest mspm0 条目补 pins（PA8/PA9）+ notes 更新（与 digit_uart 共享 DIGIT_UART）
- [x] 测试：ball mspm0 pins/syscfg 一致 + DIGIT_UART 共享消费映射
- [x] 真机 mspm0 gmake 0 错（ball_detect 单独 + 与 digit_uart 同选 UART1 聚合）
- [x] pytest 全绿 + mypy src 干净


## Comments

- ball_detect 代码逻辑未动，只补 mspm0 pins 声明 + 头注释（UART1 聚合说明）+ manifest notes。
- 真机验收：`python .scratch/module-functionalize/verify_digit_ball_mspm0.py`（digit+ball 共享 UART1）与 `python .scratch/module-functionalize/verify_protocol_mspm0.py all`（五模块三 UART 同工程）均 gmake exit=0；0 error，warnings 均为 syscfg ovsRate 基线建议。日志在 `.scratch/module-functionalize/out_digit_ball_mspm0/gmake_build.log` 与 `out_all_mspm0/gmake_build.log`。