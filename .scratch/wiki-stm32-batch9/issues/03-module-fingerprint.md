# 03 — fingerprint 指纹识别传感器（真实 UART 帧协议，手册 sensor--fingerprint-recognition-sensor.md）

**要做什么：** 模块库 `fingerprint` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼指纹识别驱动为纯驱动切片（**真实 UART**——57600、帧头 EF01FFFFFF + PID/Len/指令/校验；响应 12/16 字节、[9]=确认码、[10..11]=ID），API 与 mspm0 版**同名同型完全对齐（fingerprint.h 全族核验）**：`fingerprint_init()/check_device()/is_touched()/get_image()/img_to_buffer(buffer_id)/reg_model()/search()→uint16_t/save_finger(store_id)/delete_all()/enroll(store_id)`（+ mspm0 .h 其余函数照搬——实施者以 fingerprint.h 终校全族）；响应帧**精确收 12/16 字节**（mspm0 改进沿用——页面 200ms 稳定等待 + `u2_recv_length++` 无上限修正为精确收齐）。

**关键事实（%TEMP%\batch9-facts.md）：** F1；57600（页面取证）；页面散文 PA8/PA9 vs 代码 PA2/PA3 **自相矛盾**（notes——不照抄）；**默认 UART_1（PA9/PA10，与 K230 视觉 DIGIT_UART 身份识别互替同实例同脚先例）**；`fingerprint_rx_handler` 聚合（isr.c 加 __weak 兜底 + `USART1_IRQ_CALLS` 加 `fingerprint_rx_handler();`）。

**引脚/宏：** pins `FINGERPRINT_TX`（uart_tx，default PA9）/ `FINGERPRINT_RX`（uart_rx，default PA10），macros 5 件套 `FINGERPRINT_UART/FINGERPRINT_UART_INST/FINGERPRINT_TX_GPIO/FINGERPRINT_TX_Pin/FINGERPRINT_RX_GPIO/FINGERPRINT_RX_Pin`；pin_config.h 新宏段（**值 = 宿主 UART_1 原脚**：UART_1/USART1/GPIO_A/Pin_9/GPIO_A/Pin_10——注释：与 DIGIT/COORD/UWB/HC05 共享 UART_1（互替同脚先例；波特率互斥：57600 × 115200——同选时后 init 定波特率 + 经绑定换实例，已记录）；**新 UART 角色登记 pinwriter._UART_CALLS_ROLES** + isr.c `__weak void fingerprint_rx_handler(void) {}`。

**被谁阻塞：** 无——可立即开始。

**状态：** claimed

**实施清单：**
- [ ] `library/modules/fingerprint/code/fingerprint_stm32.c/.h`（独立 stm32 头——API 全族照 mspm0 fingerprint.h；.c uart_init/uart_sendbyte + `fingerprint_rx_handler()`（聚合宏调用——`uart_getbyte` 轮询排空收精确 12/16 字节，照 mspm0 `_receive_response` 改进）；帧发送（0xEF 01 FF FF FF + PID + Len + 指令 + 校验和）；零引脚字面量）
- [ ] manifest.json platforms 增 stm32：files、dependencies ["debug_uart"?——照 mspm0 manifest 现状（fputc 依赖 debug_uart? 指纹无 printf——照 mspm0 dependencies 原样）、verified false、hardware_bound false、pins 2 行（TX/RX）、kit/source_url（wiki 原页 `.../sensor/fingerprint-recognition-sensor.html`）、notes（手册路径+原页+网盘+57600+散文/代码脚矛盾+精确收 12/16+rx_handler 聚合+UART_1 互替共享（波特率互斥）+未上板）
- [ ] pin_config.h 增 6 宏（五件套+INST）；isr.c 加 `__weak void fingerprint_rx_handler(void) {}` + USART1_IRQ_CALLS 加调用；pinwriter._UART_CALLS_ROLES 登记 FINGERPRINT_UART
- [ ] 测试 `tests/test_module_fingerprint.py`：形状（TX/RX pins）+宏存在（`FINGERPRINT_UART\s+UART_1` 五件套）+**isr.c 聚合断言**（`fingerprint_rx_handler` __weak + USART1_IRQ_CALLS 含调用）+单选生成+mspm0 零改动+守卫（`57600`、帧头 `0xEF 0x01 0xFF 0xFF 0xFF`、精确收 12/16（无 `u2_recv_length` 无界式）、API ≥10 函数名断言、无 printf/GPIO_Init/RCC_）
- [ ] test_pins.py 补 6 宏；test_pin_bindings uart 共享组扩充（FINGERPRINT → UART1——照批 8 适配先例）；test_default_layout 白名单 UART1 外设级 +1
- [ ] UV4 矩阵（init+check_device+is_touched+get_image+img_to_buffer(0)+reg_model+search+save_finger(1)+delete_all+enroll(1) 全调，(void) 化——search 返 uint16_t）→ 0/0 → verified=true
- [ ] wordlist 零补录复核；中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
