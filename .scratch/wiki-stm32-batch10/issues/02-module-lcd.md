# 02 — lcd 六屏合一彩屏（软 SPI 6 脚 + 库内字库复用，手册五篇彩屏页）

**要做什么：** 模块库 `lcd` 新增 **stm32 平台条目**（mspm0 零改动——**字库/驱动结构直接复用 mspm0 已入库文件**）：从地阔星五篇彩屏页（0-96/1-28/1-3/1-47/1-69）提炼驱动为纯驱动切片（软 SPI 6 脚位操作——不占硬件 SPI/TIMER），API 与 mspm0 版**同名同型完全对齐（lcd.h 核验）**：`lcd_init(model, dir)`（LCD_MODEL_096/128/130/147/169/180 = ST7735/GC9A01/ST7789V2×2/ST7789V3/ST7735S；LCD_DIR_DEFAULT=0xFF）+ `lcd_get_width/height` + `lcd_fill/clear/draw_point/line/rectangle/circle` + `lcd_show_char/string/num/float/chinese16x16/picture`。

**关键事实（%TEMP%\batch10-facts.md）：** 1-47/0-96 两页软 SPI 块 **F4 混写**（改 F1）；0-96 页**连 SCLK/MOSI 宏都没给**（只有 RES/DC/CS/BLK——页内 lcd.c 自带? mspm0 版已有完整六脚——stm32 照 mspm0 结构）；**字库 = 库内 lcdfont.h（mspm0 已入库 15.9KB——stm32 直接复用**：stm32 files 含 code/lcd.c/lcd.h/lcd_init.c/lcd_init.h/lcdfont.h（**双平台共享文件先例 filter.c**——mspm0 与 stm32 同一份文件，stm32 实现只换总线层：mspm0 侧 lcd.c 用 DL_GPIO → stm32 侧用途? 拆分：**共享 = 字库/表/绘制层纯 C 部分；总线宏差异 = `#ifdef` 或 stm32 版文件**——照 mspm0 批 12 结构：lcd.c 绘制层（纯 C 可共享）+ lcd_init.c 表（共享）+ lcdfont.h（共享）；总线原语 = lcd 模块内宏族（mspm0 DL 版/stm32 gpio_set 版——**stm32 文件 = code/lcd_stm32.c/.h（总线层+API 实现**，绘制层 lcd.c 若含 mspm0 专属调用则 stm32 独立实现（实施时以 mspm0 .c 读盘为准——**工单要求：stm32 用独立 code/lcd_stm32.c/h + files 共享 lcdfont.h/lcd_init.c（若纯 C）——实施时按实际分层拆分，notes 记录**）。

**引脚与默认脚（互替同脚组）：**
- pins：`LCD_SCL`（gpio_out，default **PB4**）/ `LCD_SDA`（gpio_out，**PB5**）/ `LCD_RES`（**PA5**）/ `LCD_DC`（**PB6**）/ `LCD_CS`（**PB7**）/ `LCD_BLK`（**PA15**），macros 12 个（逐脚端口宏——跨端口逐脚宏族，照批 2 先例）。
- pin_config.h 12 宏（GPIO_A/Pin_5、GPIO_A/Pin_15、GPIO_B/Pin_4-7——注释：六脚叠「继电器+编码器方向（PB4）/称重+旋钮+编码器（PB5）/火焰+ADC 组（PA5——屏×火焰不同框）/舵机+巡线（PB6）/人体红外（PB7）/蜂鸣（PA15）」；**与 oled SPI/max7219 显示族互替同脚（一次选一块屏）**；与 tp（配套件）刻意错开；同选经绑定消解）。

**被谁阻塞：** 无——可立即开始（本批最重件）。

**状态：** resolved（2026-09 实施完成）。

**实施清单：**
- [x] `library/modules/lcd/code/lcd_stm32.c/.h`（独立 stm32 头——API 全族照 mspm0 lcd.h；.c 软 SPI 六脚位操作 + 初始化序列表（照 lcd_init.c 模型表——**共享或 stm32 拷贝**按实施分层）；字库 lcdfont.h 复用（files 共享或拷贝——**双平台共享先例**）；零引脚字面量）
- [x] manifest.json platforms 增 stm32：files（按分层定：`[code/lcd_stm32.c, code/lcd_stm32.h]` + 共享文件视分层）、dependencies ["delay"]（照 mspm0）、verified false、hardware_bound false、pins 6 行、kit/source_url（wiki 原页——五篇页对应 slug 记 notes 5 条：0-96-color/1-28-round/1-3-color/1-47-color/1-69-color + 1.8 触摸页屏侧）、notes（手册路径×5+原页+网盘×5+**六屏合一（同芯片同 API 变体——mspm0 决策 A）**+F4 混写甄别记录+字库复用（lcdfont.h 库内）+0-96 页无 SCLK/MOSI 宏记录+默认脚推理+未上板）
- [x] pin_config.h 增 12 宏
- [x] 测试 `tests/test_module_lcd.py`：形状（6 pins/files 含 lcdfont.h）+宏存在+单选生成+mspm0 零改动+守卫（`LCD_MODEL_096`..`LCD_MODEL_180` 六模型、`LCD_DIR_DEFAULT 0xFF`、字库体积 ≤16KB 断言（lcdfont.h 存在——mspm0 先例）、无演示位图数组、无 printf/GPIO_Init/RCC_）
- [x] test_pins.py 补 12 宏；test_default_layout.py 白名单 PB4/5/6/7 +4、PA5 +1、PA15 +1（显示组登记）
- [x] UV4 矩阵（init(LCD_MODEL_096, LCD_DIR_DEFAULT)+get_width/height+fill+clear+draw_point+line+rectangle+circle+show_char+show_string+show_num+show_float+show_chinese16x16+show_picture 全调，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论（2026-09 实施完成）**：stm32 条目落地——code/lcd_stm32.c/.h（**分层 = 单文件自实现**：mspm0 lcd.c 绘制层纯 C 但 include mspm0 专属 lcd_init.h（不可用）→ 绘制层/序列表/模型表自 mspm0 两件逐行移植零魔改、仅总线层换 gpio_set + 六脚 OUT_PP 初始化；**lcdfont.h 双平台共用同一份文件**（files 含 code/lcdfont.h））；API 与 mspm0 版同名同型完全对齐（lcd.h 核验 14 函数）；默认脚 SCL=PB4/SDA=PB5/RES=PA5/DC=PB6/CS=PB7/BLK=PA15（与 oled SPI 五脚组/max7219 三脚组显示族互替同脚；与 tp 配套件刻意错开）；F4 混写甄别（0-96/1-47 两页软 SPI 块 F4 → F1 改写）记录；pin_config.h 12 宏 + 测试全绿（含字库 ≤16KB 断言）；UV4 矩阵 0 error/0 warning → verified=true（run_lcd_matrix.py——Code=3760/RO=5980）；wordlist 零补录复核。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
