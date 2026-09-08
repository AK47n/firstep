# 05 — neo_6m GPS 定位模块（B 类新 slug · 仅 stm32 · NMEA 帧解析，手册 rf--neo-6m-gps-module.md）

**要做什么：** 模块库新增 **`neo_6m`**（库内无此模块——B 类，**仅 stm32 平台条目**）：从地阔星页面提炼 NEO-6M GPS 驱动为纯驱动切片（**真实 UART 9600 + NMEA 帧识别**——`$`→GPRMC→`\n` 帧识别 + 主循环字段解析（页面代码形态，非 AT）），API：`neo_6m_init()`（串口初始化）+ `neo_6m_read_frame()`（uint8_t 0=无帧/1=收到完整 GPRMC 帧）+ `neo_6m_get_position(float *lat, float *lon)`（GPRMC 字段解析——`ddmm.mmmm` → 十进制度 + 南北/东西半球符号：lat=N+S-、lon=E+W-）+ `neo_6m_clear()`（缓冲清除）。

**关键事实（%TEMP%\batch9-facts.md）：** F1；9600；默认 **UART_1（PA9/PA10，与 UWB 定位互替同实例同脚先例）**；`neo_6m_rx_handler` 聚合（isr.c __weak + USART1_IRQ_CALLS）；**缺陷修正**：① GPSRX_LEN 夹 255 后下标 255 **越界**（→接收缓冲 256 + 截断保护）；② memcpy 80 字节无长度检查（→截断）。

**引脚/宏：** pins `NEO_6M_TX`（uart_tx，default PA9）/ `NEO_6M_RX`（uart_rx，default PA10），macros 6 件套（NEO_6M_UART/UART_INST/TX_GPIO/TX_Pin/RX_GPIO/RX_Pin）；pin_config.h 新段（值 = UART_1 原脚；注释：与 DIGIT/COORD/UWB/HC05/FINGERPRINT 共享 UART_1（GPS×视觉/数传/手机遥控互替同脚先例；波特率互斥 9600——同选时后 init 定；同选经绑定换实例））；**pinwriter._UART_CALLS_ROLES 登记 NEO_6M_UART** + isr.c `__weak void neo_6m_rx_handler(void) {}` + USART1_IRQ_CALLS 调用。

**被谁阻塞：** 无——可立即开始。

**状态：** claimed

**实施清单：**
- [ ] `library/modules/neo_6m/` 新目录：`code/neo_6m_stm32.c/.h`（API 4 函数；.c uart 初始化/收发 + `neo_6m_rx_handler`（排空收字符入缓冲（256 上限+截断））+ 帧识别（`$`→GPRMC→`\n`）+ get_position 解析（GPRMC 字段 3/4：纬度 ddmm.mmmm、5：N/S、6：经度、7：E/W——十进制度换算）；零引脚字面量/零标准库）
- [ ] `manifest.json`（**仅 platforms.stm32**：files、dependencies []（无额外——串口经 ml_uart；照 B 类口径）、verified false、hardware_bound false、pins 2 行、kit（NEO-6M GPS 模块）、source_url `https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/neo-6m-gps-module.html`、notes（**B 类：无 mspm0 条目（仅 stm32）**+手册路径+原页+网盘+NMEA 解析范围（GPRMC 仅位置——日期/时间/速度字段范围外）+**255 越界/80 缓冲截断修正**+rx_handler 聚合+UART_1 互替共享+未上板）+ description（能力方向：GPS 定位/位置解析；无题绑定）
- [ ] pin_config.h 增 6 宏；isr.c 加 __weak + USART1_IRQ_CALLS；pinwriter._UART_CALLS_ROLES 登记
- [ ] 测试 `tests/test_module_neo_6m.py`（B 类模板）：仅 platforms.stm32 + pins 2 行 + 宏存在（`NEO_6M_UART\s+UART_1` 五件套）+isr.c 聚合断言+**stm32 单选生成全流程**+守卫（缓冲 256 截断（无 `[255]` 越界式）、`GPRMC` 帧头、`ddmm` 解析注释、API 4 函数断言、无 printf/GPIO_Init/RCC_/RX 越界式）
- [ ] test_pins.py 补 6 宏；test_pin_bindings uart 共享组扩充（NEO_6M → UART1）；test_default_layout 白名单 UART1 外设级 +1
- [ ] UV4 矩阵（init+read_frame+get_position(&lat,&lon)+clear，(void) 化）→ 0/0 → verified=true
- [ ] wordlist 补录（无线通信/GPS 定位 + models + lib_modules——B 类）
- [ ] 中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
