# 02 — hc05 蓝牙串口透传（UART 中断环形缓冲 + STATE/KEY，手册 rf--hc05-bluetooth-module.md）

**要做什么：** 模块库 `hc05` 新增 **stm32 平台条目**（mspm0 零改动）：API 与 mspm0 完全对齐（hc05_init / hc05_send_char|string|buffer / hc05_available / hc05_receive / hc05_clear_rx / hc05_is_connected / hc05_at_mode_enter|exit；HC05_RX_BUF_SIZE 128u、HC05_CONNECTED_LEVEL 1）。RX 中断环形缓冲（`hc05_rx_handler` 进 isr.c 聚合——**本批首次扩展 `_UART_CALLS_ROLES` + 母版 isr.c `__weak`**）；9600（HC05 出厂默认；页面代码 115200 与 AT 默认 38400 不一，mspm0 已定 9600——沿）；STATE=gpio_in、KEY=gpio_out（AT 切换 = KEY 高 + 重上电，HC05 硬件行为）。

**关键事实（F1 页 + mspm0 库内）：** F1 页默认 = 串口2（PA2/PA3）+ STATE=PA7——**不照抄**（DEBUG_UART 常备件；PA7=GRAY_D8/human_ir）。**UART 实例仲裁：默认 UART_1（UWB_UART 宿主）**——mspm0 定稿 HC05 与 UWB（UART2 同外设）互替、同选概率最低；stm32 URB=UART_1 → 同款推理挂 UART_1（TX=PA9/RX=PA10——互替件同脚先例，与 DIGIT/COORD 并列默认共享 = 合法先例、门禁只查用户绑定）。STATE=PA8（mspm0 同脚 PA8 语义：与 IR_BEAM/WS2812/GRAY_D5 默认重叠、同选概率最低）；KEY=PB4（与 RELAY/MOTOR_A_ENC_DIR 重叠、AT 切换不常用）。

**引脚：** pins `HC05_TX`（uart_tx，PA9，macros `[HC05_UART, HC05_UART_INST, HC05_UART_TX_GPIO, HC05_UART_TX_Pin]`）、`HC05_RX`（uart_rx，PA10，macros `[HC05_UART_RX_GPIO, HC05_UART_RX_Pin]`）、`HC05_STATE`（gpio_in，PA8，macros `[HC05_STATE_GPIO, HC05_STATE_PIN]`）、`HC05_KEY`（gpio_out，PB4，macros `[HC05_KEY_GPIO, HC05_KEY_PIN]`）。

**被谁阻塞：** 无——可立即开始（pinwriter 聚合表扩展与母版 isr.c 属本件范围）。

**状态：** resolved

**结论回填（2026-09-07）：全部完成。stm32 条目 = UART 中断环形缓冲件：API 与 mspm0 全对齐（hc05_init/send_char|string|buffer/available/receive/clear_rx/is_connected/at_mode_enter|exit——hc05.h 现名逐字对齐；HC05_RX_BUF_SIZE 128u + HC05_CONNECTED_LEVEL 1 + 新增 HC05_BAUDRATE 9600）。**UART 实例仲裁 = UART_1（UWB_UART 宿主，TX=PA9/RX=PA10）**：mspm0 定稿「HC05 与 UWB 同外设互替」先例的 stm32 同款推理（stm32 的 UWB = UART_1）；默认×默认共享合法（门禁只查用户绑定——DIGIT/COORD/HC05 共 UART_1 并列登记白名单）；F1 页默认串口2（PA2/PA3）不照抄。**生成侧首次扩展**：pinwriter `_UART_CALLS_ROLES` 增 `HC05_UART→hc05_rx_handler` + 母版 isr.c `__weak void hc05_rx_handler(void) {}` + 母版 pin_config.h `USART1_IRQ_CALLS` 增 hc05 —— **hc05_rx_handler 定义在模块内、由 isr.c 聚合调用（main.c 写 USART1_IRQHandler 会被 `_check_no_usart_handlers_in_main` 拦）**；test_pin_unlock_uart 三处期望串更新（swap 重分组含 hc05）；**注释区 `USART_*/GPIO_*` 含 `*/` 提前终结块注释——UV4 首轮 10 错误，改为「USART 与 GPIO API 换算」措辞后 0/0**。STATE=PA8（mspm0 同脚语义：IR_BEAM/WS2812/GRAY_D5 低频）、KEY=PB4（RELAY/编码器方向低频、AT 切换不常用；F1 页 STATE=PA7 不照抄）。页面 115200/38400 波特率矛盾 → 9600 定稿（mspm0 同）。verified=true（UV4 0 error/0 module warning，2026-09-07，3fab7d0c）+ kit/source_url + notes（手册/原页/网盘/9600/UART1 仲裁/聚合登记/默认脚推理/未上板）；wordlist 零补录；mspm0 零改动；description 双平台化；test_pins 宏表 +HC05 十宏 + CALLS 串更新、test_default_layout PA9/PA10/PA8/PB4 白名单 +hc05（分组断言同步）。

**实施清单：**
- [ ] `library/modules/hc05/code/hc05_stm32.c/.h`（uart_pin_init_ex + uart_baud_config 9600；hc05_rx_handler 环形缓冲（`% HC05_RX_BUF_SIZE`，满丢新字节）；send 走 uart_sendbyte；STATE/KEY 走 gpio_init/get/set；init 置 KEY 低 = 透传）
- [ ] `src/contest_generator/pinwriter.py` `_UART_CALLS_ROLES` 增 `("HC05_UART", "hc05_rx_handler")`
- [ ] 母版 `isr.c` 增 `__weak void hc05_rx_handler(void) {}`；母版 `pin_config.h` 增 HC05 宏段 + `USART1_IRQ_CALLS` 增 hc05_rx_handler()
- [ ] manifest.json platforms 增 stm32（files、dependencies []、verified false、hardware_bound false、pins 4 行、kit/source_url 地阔星原页、notes：手册/原页/网盘/9600 定稿+页面 115200 记录/UART1 仲裁+互替同脚/STATE=PA8/KEY=PB4 推理/环形缓冲+AT 硬件行为/未上板）
- [ ] 测试 `tests/test_module_hc05.py`（形状+宏存在+单选生成+mspm0 零改动+守卫：`HC05_RX_BUF_SIZE 128u`、`9600`、`hc05_rx_handler`、`% HC05_RX_BUF_SIZE`、无 IRQHandler 定义（聚合归 isr.c ——门禁 `_check_no_usart_handlers_in_main` 语义）、无 BSP_BLUETOOTH）
- [ ] test_pins.py 补 10 宏 + USART1_IRQ_CALLS 更新；test_default_layout.py PA9/PA10/PA8/PB4 登记
- [ ] UV4 矩阵 0/0 → verified=true
- [ ] wordlist 零补录复核；中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0；mspm0 零改动；`_regroup_irq_calls` 重分组路径不回归（test_pins USART1_IRQ_CALLS 钉值更新）。
