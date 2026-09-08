# 02 — syn6288 语音合成模块（软 UART TX，手册 control--syn6288-speech-synthesis-broadcast-module.md）

**要做什么：** 模块库 `syn6288` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼语音合成驱动为纯驱动切片（**软 UART TX**——照 mspm0 定稿 104us/bit；只发不收），API 与 mspm0 版**同名同型完全对齐（syn6288.h 核验）**：`syn6288_init()` + `syn6288_send_cmd(uint8_t cmd_type, uint8_t cmd_par, const char *text)`（页面帧：0xFD + Len(text+3) + Cmd + Par + text + XOR——**与 mspm0 逐字节一致**）+ `syn6288_speak(const char *text)`（组合帧封装）+ `syn6288_stop/pause/resume`（6 函数）。

**关键事实（%TEMP%\batch9-facts.md）：** F1；页面=真实 UART2 帧（与 mspm0 一致）+ 一线 GPIO；mspm0 定稿=软 UART TX；**strlen 无上限溢 Send_Buff[210]（mspm0 已加 200 上限——stm32 沿用）**；页面 RX (len+1)%MAX 回绕+IDLE 不清 LEN——不实现 RX（notes）；页面默认脚不照抄。

**引脚：** pins `SYN6288_TX`（gpio_out，default **PC14**，macros `[SYN6288_GPIO, SYN6288_PIN]`）；pin_config.h：`#define SYN6288_GPIO GPIO_C` / `#define SYN6288_PIN Pin_14`（注释：默认 PC14 叠 LED_YELLOW——输出指示互替、同选概率最低；与 jq8900（PA15）互相错开；同选经绑定消解）。

**被谁阻塞：** 无——可立即开始（与 jq8900 对仗）。

**状态：** claimed

**实施清单：**
- [ ] `library/modules/syn6288/code/syn6288_stm32.c/.h`（独立 stm32 头——API 6 函数与 mspm0 syn6288.h 同名同型；.c 软 UART TX（104us/bit）+ send_cmd 帧（0xFD/Len/Cmd/Par/text/XOR）+ **text 长度 ≤200 上限**（Send_Buff 防溢出）；零引脚字面量/零标准库/无 UART 实例字面量）
- [ ] manifest.json platforms 增 stm32：files、dependencies ["delay"]、verified false、hardware_bound false、pins 1 行、kit/source_url（wiki 原页 `.../control/syn6288-speech-synthesis-broadcast-module.html`）、notes（手册路径+原页+网盘+软 UART TX 定稿+200 上限（mspm0 同款）+RX 不实现+默认脚推理+未上板）
- [ ] pin_config.h 增 2 宏
- [ ] 测试 `tests/test_module_syn6288.py`：形状+宏存在（`SYN6288_GPIO\s+GPIO_C`/`SYN6288_PIN\s+Pin_14`）+单选生成+mspm0 零改动+守卫（`104`us、`0xFD` 帧头+异或校验+`200` 上限、API 6 函数名断言、无 `UART_`/`USART`/`rx_handler`、无 printf/GPIO_Init/RCC_）
- [ ] test_pins.py 补 2 宏；test_default_layout.py 白名单 PC14 +1（LED 组）
- [ ] UV4 矩阵（init+send_cmd(1,0,"test")+speak("hi")+stop+pause+resume 全调，(void) 化）→ 0/0 → verified=true
- [ ] wordlist 零补录复核；中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
