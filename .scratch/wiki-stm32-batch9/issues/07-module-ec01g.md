# 07 — ec01g NB-IoT+GPS 模块（B 类新 slug · 仅 stm32 · AT 透传，手册 rf--ec01g-nbiot-gps-module.md）

**要做什么：** 模块库新增 **`ec01g`**（库内无此模块——B 类，**仅 stm32 平台条目**）：从地阔星页面提炼 EC-01G 驱动为纯驱动切片（**真实 UART 9600 + AT 指令透传 + hex 响应解码**（页面 NB-IoT HTTP 天气 demo 形态——**demo 本体归范围外**，仅保留 AT 收发底座），API：`ec01g_init()` + `ec01g_send_cmd(const char *cmd)`（AT 行 + 应答匹配 strstr+超时——页面原式）+ `ec01g_send_string(const char *s)`（透传）+ `ec01g_available()` + `ec01g_receive(uint8_t *buf, uint16_t max_len)`（截断保护）。

**关键事实（%TEMP%\batch9-facts.md）：** F1；9600；**页面无 GPS 代码**（NB-IoT+GPS 模块但 demo 仅 HTTP 天气——GPS 归范围外）；默认 **UART_3（PB10/PB11，与 ZIGBEE/AS32 无线互替同实例同脚先例）**；`ec01g_rx_handler` 聚合；**缺陷修正**：① 超时后 `rev_buff=NULL→+=11` **空指针崩溃**（→接收缓冲非空指针保护）；② `Search_Data while(!='"')` 无界扫（→有界）+ 补零位错 `[i+1]`（→按页面语义修正或裁剪 demo 不落）；hex 响应解码细节保留（页面原式——解码函数随 AT 底座保留或范围外按实施判断（demo 级不落，解码原语若独立可留）。

**引脚/宏：** pins `EC01G_TX`（uart_tx，default PB10）/ `EC01G_RX`（uart_rx，default PB11），macros 6 件套（EC01G_UART 等）；pin_config.h 新段（值 = UART_3 原脚；注释：与 ZIGBEE/AS32 无线互替同脚先例；波特率互斥 9600；同选经绑定换实例）；pinwriter._UART_CALLS_ROLES 登记 + isr.c `__weak void ec01g_rx_handler(void) {}` + USART3_IRQ_CALLS 调用。

**被谁阻塞：** 无——可立即开始。

**状态：** claimed

**实施清单：**
- [ ] `library/modules/ec01g/` 新目录：`code/ec01g_stm32.c/.h`（API 5 函数；.c uart 收发 + rx_handler（收缓冲 256 上限+截断——空指针保护）+ send_cmd 应答匹配（strstr+超时）；零引脚字面量/零标准库）
- [ ] `manifest.json`（仅 platforms.stm32：files、dependencies []、verified false、hardware_bound false、pins 2 行、kit（EC-01G NB-IoT+GPS 模块）、source_url `.../rf/ec01g-nbiot-gps-module.html`、notes（B 类口径+手册路径+原页+网盘+**页面无 GPS 代码（GPS 归范围外）**+天气/JSON demo 归范围外+缺陷修正（空指针/无界扫）+rx_handler+UART_3 互替共享+未上板）+ description（能力方向：NB-IoT 通信/AT 指令；无题绑定）
- [ ] pin_config.h 增 6 宏；isr.c __weak + USART3_IRQ_CALLS；pinwriter 登记
- [ ] 测试 `tests/test_module_ec01g.py`（B 类模板）：仅 platforms.stm32 + 宏存在（`EC01G_UART\s+UART_3` 五件套）+isr.c 聚合（USART3_IRQ_CALLS 含 ec01g）+单选生成+守卫（空指针保护（`NULL`/非空检查）、有界扫、`strstr` 匹配、缓冲上限、API 5 函数断言、无 printf/GPIO_Init/RCC_）
- [ ] test_pins.py 补 6 宏；test_pin_bindings uart 共享组扩充（EC01G → UART3）；test_default_layout 白名单 UART3 外设级 +1
- [ ] UV4 矩阵（init+send_cmd("AT")+send_string("x")+available+receive(buf,128)，(void) 化）→ 0/0 → verified=true
- [ ] wordlist 补录（无线通信/NB-IoT + models + lib_modules）
- [ ] 中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
