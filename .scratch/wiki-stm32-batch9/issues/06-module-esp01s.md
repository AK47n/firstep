# 06 — esp01s WiFi 模块（B 类新 slug · 仅 stm32 · AT 透传，手册 rf--esp01s-wifi-module.md）

**要做什么：** 模块库新增 **`esp01s`**（库内无此模块——B 类，**仅 stm32 平台条目**）：从地阔星页面提炼 ESP-01S 驱动为纯驱动切片（**真实 UART 115200 + AT 指令透传 + strstr 应答匹配 + `+IPD,` 数据解析**），API：`esp01s_init()`（串口初始化）+ `esp01s_send_cmd(const char *cmd)`（发送 AT 行 + 等待应答（`OK`/`ERROR`/`+...` strstr 匹配 + 超时——页面原式；uint8_t 0=超时/1=OK）+ `esp01s_send_string(const char *s)`（透传数据，如 AT+CIPSEND 后负载）+ `esp01s_available()`（有数据返回 1）+ `esp01s_receive(uint8_t *buf, uint16_t max_len)`（回读 +IPD 负载——截断保护）+ `esp01s_parse_ipd`（+IPD,len: 载荷提取——页面原式保留核心）。

**关键事实（%TEMP%\batch9-facts.md）：** F1；115200；默认 **UART_1（与 HC05 手机遥控互替同实例同脚先例）**；`esp01s_rx_handler` 聚合；**缺陷修正**：① RX `(len+1)%200` 回绕覆盖（→缓冲 200+ 截断）；② IDLE `'\0'` 断串（→按长度/帧界）；③ `while(':')` 无界扫（→有界）；④ buff[50] 截断 200 数据（→上限 200）；**AT 模板（CWMODE/CWSAP/CIPSERVER/connect）与 MQTT/阿里云/JSON 归骨架/范围外**（页面 demo 均不落）。

**引脚/宏：** pins `ESP01S_TX`（uart_tx，default PA9）/ `ESP01S_RX`（uart_rx，default PA10），macros 6 件套（ESP01S_UART 等——照 fingerprint 五件套+INST）；pin_config.h 新段（值 = UART_1 原脚；注释：与 HC05 手机遥控互替同脚先例；波特率互斥 115200；同选经绑定换实例）；pinwriter._UART_CALLS_ROLES 登记 + isr.c `__weak void esp01s_rx_handler(void) {}`。

**被谁阻塞：** 无——可立即开始（B 类 AT 首件，打样）。

**状态：** claimed

**实施清单：**
- [ ] `library/modules/esp01s/` 新目录：`code/esp01s_stm32.c/.h`（API 6 函数；.c uart 收发 + rx_handler（收字符入缓冲 200 上限+截断）+ send_cmd 应答匹配（strstr+超时）+ parse_ipd（`+IPD,` 有界解析）；零引脚字面量/零标准库）
- [ ] `manifest.json`（仅 platforms.stm32：files、dependencies []、verified false、hardware_bound false、pins 2 行、kit（ESP-01S WiFi 模块）、source_url `.../rf/esp01s-wifi-module.html`、notes（B 类口径+手册路径+原页+网盘（5 条）+AT 模板/应用范围外+缺陷修正 4 条+rx_handler+UART_1 互替共享+未上板）+ description（能力方向：WiFi 连接/AT 透传；无题绑定）
- [ ] pin_config.h 增 6 宏；isr.c __weak + USART1_IRQ_CALLS；pinwriter 登记
- [ ] 测试 `tests/test_module_esp01s.py`（B 类模板）：仅 platforms.stm32 + 宏存在（`ESP01S_UART\s+UART_1` 五件套）+isr.c 聚合+单选生成+守卫（无 `% 200` 回绕式、有界扫（`while` 含上限条件）、`strstr` 匹配、缓冲 200 上限、API 6 函数断言、无 printf/GPIO_Init/RCC_）
- [ ] test_pins.py 补 6 宏；test_pin_bindings uart 共享组扩充（ESP01S → UART1）；test_default_layout 白名单 UART1 外设级 +1
- [ ] UV4 矩阵（init+send_cmd("AT")+send_string("hi")+available+receive(buf,128)+parse_ipd，(void) 化）→ 0/0 → verified=true
- [ ] wordlist 补录（无线通信/WiFi + models + lib_modules）
- [ ] 中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
