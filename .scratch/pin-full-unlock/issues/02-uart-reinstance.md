# 02 — stm32 UART 换实例（类型级 + TX/RX 对 + 实例冲突门禁 + isr.c + fputc）

**What to build:** UART 角色解锁到任意 uart 能力脚——pin_bindings 对 uart 类型级化（TX/RX 对同实例交集校验）；ml_uart 引脚参数化（uart_pin_init_ex + fputc 跟随 DEBUG_UART）；母版新增静态 isr.c（USARTx_IRQHandler 胶水，聚合宏入 pin_config.h 渲染面）；实例冲突门禁拦撞车。

**Blocked by:** 01（pin_bindings.py / tests / index.html 同缝——01 合 main 后再开）

**Status:** 待实施

## 需求

1. **pin_bindings.py uart 类型级**：uart_tx/uart_rx 角色入类型级分支——绑定脚须有对应 uart 类型 token；**TX/RX 对同实例约束**：两脚 token 实例集交集非空（空 → 400 中文"TX/RX 必须同实例，请成对绑定"）；实例 = 交集推导喂渲染器 `_UART`/`_INST` 尾形。
2. **门禁 `_check_uart_instance_conflicts` 入 GENERATION_GATES**：绑定 UART 角色推导实例 × **未绑定** UART 角色默认实例 → 400 中文（如"DEBUG_UART 绑 UART_3 与 ZIGBEE_UART 默认实例冲突"）；绑定×绑定同实例放行（共享提示语义，换位合法）；默认×默认不查（DIGIT/BALL/UWB 共 UART_1 现状合法）。
3. **ml_uart.c 参数化**：fputc 改 `DEBUG_UART_INST->SR/DR`（:31-36，include pin_config.h）；新增 `uart_pin_init_ex(uart_n, tx_gpio, tx_pin, rx_gpio, rx_pin)`（RCC/NVIC 公式沿用 :101-109），旧 `uart_pin_init` 保留不动（switch 表仍在，供旧调用方）。
4. **模块 init 调用点切换**：debug_uart.c / uwb_uart.c / zigbee_uart.c / digit_uart.c / ball_detect_stm32.c 的 stm32 init 改调 uart_pin_init_ex + 传各自 TX/RX 宏（宏名按 pin_config.h 新键）。
5. **pin_config.h 母版**：每 UART 角色 +4 宏（`DEBUG_UART_TX_GPIO GPIO_A` / `_TX_Pin Pin_2` / `_RX_GPIO GPIO_A` / `_RX_Pin Pin_3`，值 = 现 switch 表引脚，原值不变）；+3 聚合宏：`USART1_IRQ_CALLS` = digit_uart_rx_handler(); ball_detect_rx_handler(); uwb_uart_rx_handler();（默认序）/ `USART2_IRQ_CALLS` = debug_uart_rx_handler(); / `USART3_IRQ_CALLS` = zigbee_uart_rx_handler();。
6. **isr.c 母版新增**（library/masters/stm32/isr.c）：`#include "pin_config.h"` + 5 个 `__weak void *_rx_handler(void){}` 兜底 + `void USART1_IRQHandler(void){ USART1_IRQ_CALLS }` ×3 实例。**模块 rx_handler 必须非 static**（工单核查并修正）。uvprojx 确定性渲染器文件树全 .c 引用 → 自动纳入（真机验证）。
7. **pinwriter.py 渲染器扩展**：新尾形 `_IRQ_CALLS`（重分组：按各 UART 角色绑定实例把 rx_handler 调用归入对应 USARTx_IRQ_CALLS；未绑角色按默认实例）+ `_TX_GPIO/_TX_Pin/_RX_GPIO/_RX_Pin` 四尾形（值推导复用 `_stm32_macro_value` 同源）。
8. **manifests 补 macros**：digit_uart / ball_detect / debug_uart / uwb_uart / zigbee_uart / zigbee_uart_key 的 TX 条目补 [_TX_GPIO, _TX_Pin]、RX 条目补 [_RX_GPIO, _RX_Pin]（default 值不动）。
9. **index.html pinCanHost 镜像**：uart 类型级（有 uart_tx/uart_rx token 的脚可选）。
10. **测试**：红证先行（缺类型级被拦 / 交集空 400 / 绑 DEBUG→UART_3 撞 ZIGBEE 默认 400）；绿证——三组绑定全换位（DEBUG→UART_3、ZIGBEE→UART_2、UWB→UART_2 成对绑 TX/RX）放行 + pin_config.h 宏值 + USARTx_IRQ_CALLS 重分组断言 + isr.c 聚合编译 + fputc 宏断言；默认不配输出 == 新母版逐字节；tests/test_pins.py uart 类型级豁免 + 宏值表 +8/角色；新增 tests/test_pin_unlock_uart.py。
11. **真机**：2026C `--reuse-recommend` ①不配回归 UV4 -r 0 错 0 警 + pin_config.h/isr.c == 新母版逐字节；②换位绑定 UV4 0 错 0 警 + 产物宏断言（printf 流已随 DEBUG_UART 挪位——验收注意串口观察位置变化）；③单角色绑 DEBUG→UART_3 → HTTP 400 中文零产物。运行级用户上板自验。

## 文件边界

- `src/contest_generator/pin_bindings.py`、`src/contest_generator/generator.py`（门禁表）、`src/contest_generator/errors.py`、`src/contest_generator/pinwriter.py`
- `library/masters/stm32/pin_config.h`、`library/masters/stm32/isr.c`（新）、`library/masters/stm32/ml_libs/ml_uart.c`
- `library/modules/{debug_uart,uwb_uart,zigbee_uart,digit_uart,ball_detect}/code/*stm32*.c`（init 调用点）、同五模块 + zigbee_uart_key 的 manifest.json
- `index.html`（pinCanHost）
- `tests/test_pin_bindings.py`、`tests/test_pins.py`（豁免/宏值表同步）、`tests/test_pin_unlock_uart.py`（新）
- 零 ml_exti / motor_stm32.c 改动；铁律：独立 worktree（01 合 main 后从最新 main 建）

## 验收

- [ ] pytest 全绿 + mypy src 干净
- [ ] 红证已验（类型级缺位 / 交集空 / 实例冲突）+ 绿证（换位放行 + 宏值 + CALLS 重分组 + fputc + 默认逐字节）
- [ ] 真机：不配回归 + 换位绑定 UV4 双 0 错 + 单角色撞车 HTTP 400 零产物
- [ ] 独立 worktree + 提交 + 推送开 PR
