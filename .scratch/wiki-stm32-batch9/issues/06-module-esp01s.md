# 06 — esp01s WiFi 模块（B 类新 slug · 仅 stm32 · AT 透传，手册 rf--esp01s-wifi-module.md）

**要做什么：** 模块库新增 **`esp01s`**（库内无此模块——B 类，**仅 stm32 平台条目**）：从地阔星页面提炼 ESP-01S 驱动为纯驱动切片（**真实 UART 115200 + AT 指令透传 + strstr 应答匹配 + `+IPD,` 数据解析**），API：`esp01s_init()`（串口初始化）+ `esp01s_send_cmd(const char *cmd)`（发送 AT 行 + 等待应答（`OK`/`ERROR`/`+...` strstr 匹配 + 超时——页面原式；uint8_t 0=超时/1=OK）+ `esp01s_send_string(const char *s)`（透传数据，如 AT+CIPSEND 后负载）+ `esp01s_available()`（有数据返回 1）+ `esp01s_receive(uint8_t *buf, uint16_t max_len)`（回读 +IPD 负载——截断保护）+ `esp01s_parse_ipd`（+IPD,len: 载荷提取——页面原式保留核心）。

**关键事实（%TEMP%\batch9-facts.md）：** F1；115200；默认 **UART_1（与 HC05 手机遥控互替同实例同脚先例）**；`esp01s_rx_handler` 聚合；**缺陷修正**：① RX `(len+1)%200` 回绕覆盖（→缓冲 200+ 截断）；② IDLE `'\0'` 断串（→按长度/帧界）；③ `while(':')` 无界扫（→有界）；④ buff[50] 截断 200 数据（→上限 200）；**AT 模板（CWMODE/CWSAP/CIPSERVER/connect）与 MQTT/阿里云/JSON 归骨架/范围外**（页面 demo 均不落）。

**引脚/宏：** pins `ESP01S_TX`（uart_tx，default PA9）/ `ESP01S_RX`（uart_rx，default PA10），macros 6 件套（ESP01S_UART 等——照 fingerprint 五件套+INST）；pin_config.h 新段（值 = UART_1 原脚；注释：与 HC05 手机遥控互替同脚先例；波特率互斥 115200；同选经绑定换实例）；pinwriter._UART_CALLS_ROLES 登记 + isr.c `__weak void esp01s_rx_handler(void) {}`。

**被谁阻塞：** 无——可立即开始（B 类 AT 首件，打样）。

**状态：** resolved

**实施清单：**
- [x] `library/modules/esp01s/` 新目录：`code/esp01s_stm32.c/.h`（API 6 函数；.c uart 收发 + rx_handler（收字符入缓冲 200 上限+截断）+ send_cmd 应答匹配（strstr+超时）+ parse_ipd（`+IPD,` 有界解析）；零引脚字面量/零标准库）
- [x] `manifest.json`（仅 platforms.stm32：files、dependencies []、verified false、hardware_bound false、pins 2 行、kit（ESP-01S WiFi 模块）、source_url `.../rf/esp01s-wifi-module.html`、notes（B 类口径+手册路径+原页+网盘（5 条）+AT 模板/应用范围外+缺陷修正 4 条+rx_handler+UART_1 互替共享+未上板）+ description（能力方向：WiFi 连接/AT 透传；无题绑定）
- [x] pin_config.h 增 6 宏；isr.c __weak + USART1_IRQ_CALLS；pinwriter 登记
- [x] 测试 `tests/test_module_esp01s.py`（B 类模板）：仅 platforms.stm32 + 宏存在（`ESP01S_UART\s+UART_1` 五件套）+isr.c 聚合+单选生成+守卫（无 `% 200` 回绕式、有界扫（`while` 含上限条件）、`strstr` 匹配、缓冲 200 上限、API 6 函数断言、无 printf/GPIO_Init/RCC_）
- [x] test_pins.py 补 6 宏；test_pin_bindings uart 共享组扩充（ESP01S → UART1）；test_default_layout 白名单 UART1 外设级 +1
- [x] UV4 矩阵（init+send_cmd("AT")+send_string("hi")+available+receive(buf,128)+parse_ipd，(void) 化）→ 0/0 → verified=true
- [x] wordlist 补录（无线通信/WiFi + models + lib_modules）
- [x] 中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。

## Comments

- 2026-09-09 补标 resolved（代码事实盘点，复核工单自述）：
  新目录落盘 `library/modules/esp01s/`（manifest.json 6074B +
  `code/esp01s_stm32.c` 5481B + `esp01s_stm32.h` 4651B）；头文件 50-72 行 API
  **6 函数 + rx_handler**（init / send_cmd→uint8_t / send_string / available /
  receive(buf,max)→uint16_t / parse_ipd(id,len,out,max)）。
  manifest 实测：`platforms=['stm32']`（B 类仅 stm32）、`stm32_files=2`、
  `verified=True`、`hardware_bound=False`、`pins=['ESP01S_TX','ESP01S_RX']`、
  kit/source_url 齐。
  pin_config.h：`:545-550` 六件套（`ESP01S_UART UART_1` / `_UART_INST USART1` /
  TX PA9 / RX PA10）；isr 聚合 `:762 USART1_IRQ_CALLS … esp01s_rx_handler();`。
  测试 `tests/test_module_esp01s.py` 6 用例（:65 形状 / :117 宏 / :132 isr __weak /
  :138 pinwriter 角色登记 / :148 stm32 单选生成 / :172 守卫）——实测全绿。
  wordlist：`wordlist.json:785/788` 已补录（无线通信组 + lib_modules `esp01s`）。
  验收逐条对照：① 新目录 + API 6 函数 + AT 透传 + 4 条缺陷修正 ✓
  ② manifest 仅 stm32 + kit/source_url + description ✓ ③ 6 宏 + isr + pinwriter ✓
  ④ 测试形状/宏/isr/生成/守卫（无回绕式、有界扫、strstr）✓ ⑤ test_pins 等 ✓
  ⑥ 矩阵 verified=true ✓ ⑦ wordlist 补录 ✓。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
