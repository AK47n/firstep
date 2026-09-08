# 01 — jq8900 语音播报模块（软 UART TX，手册 control--jq8900-voice-broadcast-module.md）

**要做什么：** 模块库 `jq8900` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼语音播报驱动为纯驱动切片（**软 UART TX**——`delay_us(104)+gpio_set` 位时序（9600 8N1 换算；照 mspm0 定稿「软 UART TX 学页面两线帧」；只发不收——语音控制命令无需响应读取；不占 UART 实例），API 与 mspm0 版**同名同型完全对齐（jq8900.h 核验）**：`jq8900_init()` + `jq8900_send_cmd(uint8_t cmd, uint8_t data)`（页面两线帧 0xAA+cmd+data+求和）+ `jq8900_play(index)/play_next/play_prev/stop/pause/resume/set_volume(volume)/volume_up/volume_down`（11 函数）。

**关键事实（%TEMP%\batch9-facts.md）：** F1；页面=真实 UART2（两线）+ 一线 GPIO 时序（3:1 脉宽）双描述；mspm0 定稿 = 软 UART TX 学两线帧（104us/bit）；页面 RX `(len+1)%MAX` 回绕覆盖首字节缺陷——**不实现 RX**（notes）；正文「bsp_syn6288」串台（notes）；页面默认脚 PA2/PA3（DEBUG 常备）不照抄。

**引脚：** pins `JQ8900_TX`（gpio_out，default **PA15**，macros `[JQ8900_GPIO, JQ8900_PIN]`）；pin_config.h：`#define JQ8900_GPIO GPIO_A` / `#define JQ8900_PIN Pin_15`（注释：默认 PA15 叠 BUZZER——语音播报与蜂鸣器为**提示输出互替**（替代而非组合）、同选概率最低（互替同脚先例：ttp224×key_matrix）；与 syn6288（PC14）互相错开；同选经绑定消解）。

**被谁阻塞：** 无——可立即开始。

**状态：** claimed

**实施清单：**
- [ ] `library/modules/jq8900/code/jq8900_stm32.c/.h`（独立 stm32 头——API 11 函数与 mspm0 jq8900.h 同名同型；.c 软 UART TX 位时序（start 位低 + LSB 先 + stop 位高，每 bit 104us）；帧 = 0xAA+cmd+data+（cmd+data 求和校验）页面原式；零引脚字面量/零标准库/无 UART 实例字面量）
- [ ] manifest.json platforms 增 stm32：files `[code/jq8900_stm32.c, code/jq8900_stm32.h]`、dependencies ["delay"]（照 mspm0 现状）、verified false、hardware_bound false、pins 1 行、kit/source_url（wiki 原页 `.../control/jq8900-voice-broadcast-module.html`）、notes（手册路径+原页+网盘+**软 UART TX 定稿（页面两线帧/104us）**+RX 不实现（回绕缺陷记录）+「bps_syn6288」串台+默认脚推理+未上板）
- [ ] pin_config.h 增 2 宏
- [ ] 测试 `tests/test_module_jq8900.py`：形状+宏存在（`JQ8900_GPIO\s+GPIO_A`/`JQ8900_PIN\s+Pin_15`）+单选生成+mspm0 零改动+守卫（`104`us、`0xAA` 帧头+求和校验、API 11 函数名断言（play/play_next/play_prev/stop/pause/resume/set_volume/volume_up/volume_down/send_cmd）、无 `UART_`/`USART`/`rx_handler`、无 printf/GPIO_Init/RCC_）
- [ ] test_pins.py 补 2 宏；test_default_layout.py 白名单 PA15 +1（BUZZER 组）
- [ ] UV4 矩阵（init+send_cmd+play(1)+play_next+play_prev+stop+pause+resume+set_volume(6)+volume_up+volume_down 全调，(void) 化）→ 0/0 → verified=true
- [ ] wordlist 零补录复核；中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
