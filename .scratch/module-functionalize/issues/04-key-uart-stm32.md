# 04 — key / uart 补 stm32 + 骨架/冒烟 prompt 输出函数约束

**What to build:** key 模块补 stm32（get_key_state(void)，默认 PB3 经引脚绑定可改，母版 pin_config.h 补 KEY_GPIO/KEY_PIN）；uart 模块补 stm32（UART_send_string/char/buffer 走 UARTn_enum，转发 ml_uart）；骨架/冒烟 prompt 补 include 前缀与输出函数约束（防 LLM 出稿带 code/ 前缀、printf/snprintf 碎片）。

**Blocked by:** 无

**Status:** resolved（2026-08-15）

- [x] key stm32 文件 + manifest（PB3，上拉低电平按下）+ mspm0 key API 改 get_key_state(void)
- [x] uart stm32 文件 + manifest（UARTn_enum）+ mspm0 uart buffer 长度统一 uint16_t
- [x] 母版 pin_config.h 补 KEY_GPIO/KEY_PIN；beep_stm32 极性改低电平触发（pin_config 约定）
- [x] prompt 约束：include 不带目录前缀；冒烟输出用 OLED_ShowString/OLED_ShowNum/debug_uart_send，不用 printf/snprintf
- [x] 测试同步（test_default_layout PB3 白名单 / test_master_embedded key stm32 回归 / test_llm prompt 钉）+ pytest 全绿 + mypy 干净
- [x] 真机：stm32/mspm0 冒烟 + 参考路径 PASS（含 key/uart）

## Comments

- 真机 mspm0 冒烟连续 3 次 FAIL：LLM 出稿用 snprintf/vsnprintf，静态自检拦掉后 main.c 碎片化。prompt 禁止 stdio 输出后 PASS。
- stm32 冒烟曾 502 后重试 PASS（验收脚本已加 3 次整段重试，不再一失败就结束）。
