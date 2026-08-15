# 02 — stm32 UART 换实例（类型级 + TX/RX 对 + 实例冲突门禁 + isr.c + fputc）

**What to build:** UART 角色解锁到任意 uart 能力脚——pin_bindings 对 uart 类型级化（TX/RX 对同实例交集校验）；ml_uart 引脚参数化（uart_pin_init_ex + fputc 跟随 DEBUG_UART）；母版新增静态 isr.c（USARTx_IRQHandler 胶水，聚合宏入 pin_config.h 渲染面）；实例冲突门禁拦撞车。

**Blocked by:** 01（pin_bindings.py / tests / index.html 同缝——01 合 main 后再开）

**Status:** resolved（2026-08-15 PR #79 squash merged eb41286，主会话复核 + 1514 绿复跑）

## 实施记录（2026-08-15，worktree pin-full-unlock-02 @ 7962fd6）

**验收全过**：pytest 1514 绿 + mypy src 干净；真机 2026C 三场景——①不配回归
UV4 0 错 0 警 + pin_config.h/isr.c == 新母版逐字节；②换位绑定（DEBUG→UART_3、
ZIGBEE→UART_2、UWB→UART_2 成对绑 TX/RX）最终 UV4 0 错 0 警 + 产物宏断言全
命中（CALLS 重分组 USART1=digit+ball / USART2=uwb+zigbee / USART3=debug，
fputc 流随 DEBUG_UART 挪位）；③单角色绑 DEBUG→UART_3 → HTTP 400 中文零产物。

**偏差留痕（边界外必要改动 / 与工单文本的差异）**：
1. **CALLS/兜底用真实函数名**：模块实际名为 `uwb_rx_handler` / `zigbee_rx_handler`
   （非需求 5 示例的 uwb_uart_rx_handler / zigbee_uart_rx_handler）——重命名
   超文件边界（.h 也要动），聚合宏与 isr.c 兜底按真实名对齐，弱兜底覆盖
   语义才成立。
2. **uart_pin_init_ex 形参 uint8_t**（需求 3 签名 5 参照旧）：ml_uart.h 里用
   GPIOn_enum/Pinx_enum 会在 ml_led.c 编译时炸（ml_led.h→ml_gpio.h→headfile.h
   →ml_uart.h 循环 include，枚举在 ml_gpio.h 的 headfile.h include 之后才定义
   ——真机 UV4 #20 undefined 4 错判例）；改 uint8_t + 定义体显式转换回枚举，
   ml_uart.h 加声明（边界外必要小改）。签名无 baud/priority 参 → 内定 115200
   （全库 UART 角色同波特率）+ NVIC 0x01（debug/digit/ball 旧 0→1，都使能
   中断，仅抢占优先级差异）。
3. **新增门禁 no_usart_handlers_in_main**（需求表外加一条，errors.py 已登记）：
   骨架 LLM 按旧模块头注释"USART1 中断调用"在 main.c 写 USARTx_IRQHandler →
   与 isr.c 强符号 UV4 L6200E multiply defined（真机判例）。修法双管：三模块
   头（uwb/zigbee/debug）.h 注释改指 isr.c 聚合（勿在 main.c 定义）+ 门禁兜底
   （main.c 定义 USART1/2/3_IRQHandler → 400 中文，骨架回归 = 生成前拦而非
   链接期炸）。mspm0 不适用。
4. **真机 ② 连带绑 zigbee_uart_key 对**：2026C 推荐集含 key 模块——key 未绑
   则其默认 UART_3 撞 DEBUG 绑 UART_3 → 400（门禁语义正确体现，换位需多角色
   同时绑）；键集 8 条（三组 + key 对）。
5. **真机 ② 首轮 UV4 有骨架缺陷**（两次跑首轮分别为 1 错 / 9 错 5 警，
   根因 = 骨架 LLM 的 `#if DEVICE_KEY_TX` 预处理块缺 `#endif`，与 uart
   改动无关）→ 修复循环 1 轮归零；终态 0 错 0 警（验收口径 = 终态编译绿 +
   产物断言）。

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

- [x] pytest 1514 绿 + mypy src 干净
- [x] 红证已验（类型级缺位 / 交集空 / 实例冲突 / main.c 禁 USARTx_IRQHandler）+ 绿证（换位放行 + 宏值 + CALLS 重分组 + fputc + isr.c 聚合 + 默认逐字节）
- [x] 真机：不配回归 UV4 0 错 0 警 + 逐字节 ✓；换位绑定 UV4 0 错 0 警 + 产物宏断言 ✓；单角色撞车 HTTP 400 零产物 ✓
- [x] 独立 worktree（pin-full-unlock-02 @ 7962fd6）
- [x] 提交 57bc541 + 推送开 PR #79（https://github.com/AK47n/firstep/pull/79）

## Comments（2026-08-15 合并复核）

- **合并复核**（PR #79 squash merged eb41286，主会话）：diff 逐项对工单——uart 类型级入 tuple（pwm/enc/uart 共用）/ TX/RX 对交集校验（绑定脚×未绑默认脚实例集，空 = 400 成对绑定，成对同实例放行）/ uart_instance_conflicts 门禁（绑定改动推导实例 × 未绑角色默认实例 400，绑定×绑定放行、no-op 跳过、默认×默认不查）/ no_usart_handlers_in_main 门禁（clex 注释剥离 + USART1/2/3 定义形态正则，mspm0 跳过）/ _regroup_irq_calls（按 {STEM}_UART 现值重分组，非 uart 绑定不碰 CALLS 行保逐字节契约）/ isr.c 5 weak + 3 handler / fputc 跟随 DEBUG_UART_INST / uart_pin_init_ex uint8_t 形参（循环 include 判例）RCC/NVIC 公式沿用 / 五模块 init 切换 + rx_handler 非 static / 六 manifest 补 macros / uvprojx 静态与渲染双路纳入；偏差五条留痕理由成立（真实 handler 名对齐、uint8_t 判例、新门禁兜底 L6200E 判例、key 连带绑 = 门禁语义正确体现、骨架 #if 缺陷与本单无关）。合并后 main 复跑 1514 绿 30.5s + mypy src 41 文件干净。worktree pin-full-unlock-02 照例保留。
