# 05 — digit_uart 补 mspm0（雏形核对 + 真机 gmake 验证）

**What to build:** digit_uart 的 mspm0 雏形（DIGIT_UART/UART1、PA8/PA9、RX 中断 + 环形缓冲 + CSV 帧解析）核对通过并落真机 gmake 0 错留痕：manifest mspm0 条目、母版 syscfg DIGIT_UART 实例、syscfg 实例消费映射三处一致；与 ball_detect 共享 UART1 时由 main.c 单个 UART1_IRQHandler 聚合两个 rx_handler。

**Blocked by:** 无（spec `.scratch/module-functionalize/spec.md` 已定稿）

**Status:** resolved（2026-08-15）

- [x] 核对 digit_uart_mspm0.c/h：include 自含、DL_UART 宏消费、init/flush/rx_handler/parse API 与 stm32 版同形
- [x] manifest mspm0 条目 pins（PA8/PA9）与母版 syscfg DIGIT_UART $assign 一致（tests/test_pins.py MSPM0_DEFAULT_MAP）
- [x] 测试新文件 `tests/test_module_protocol_mspm0.py`：digit 雏形不变量 + DIGIT_UART 共享消费映射
- [x] 真机 mspm0 gmake 0 错（DIGIT_UART 实例，UART1_IRQHandler 聚合 digit+ball）
- [x] pytest 全绿 + mypy src 干净


## Comments

- 雏形核对只改头注释（IRQ 聚合说明）与 manifest notes（共享 ball_detect 措辞）；代码逻辑未动。
- 真机验收：`python .scratch/module-functionalize/verify_digit_ball_mspm0.py` → gmake exit=0，0 error / 1 warning（基线警告）；生成日志 `.scratch/module-functionalize/out_digit_ball_mspm0/gmake_build.log`。SYSCFG_DL_init 按母版头未生成前门禁契约注释，上板取消注释。