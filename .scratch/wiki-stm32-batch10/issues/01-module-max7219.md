# 01 — max7219 数码管/点阵（软 SPI 3 脚，手册 screen--8-bit-led-tube.md + screen--max7219-matrix-display.md）

**要做什么：** 模块库 `max7219` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星两页提炼 MAX7219 驱动为纯驱动切片（软 SPI 位操作 3 脚——CLK/DIN/CS；不占硬件 SPI/TIMER），API 与 mspm0 版**同名同型完全对齐（max7219.h 核验）**：`max7219_init(form, brightness)`（FORM_DIGIT 0 / MATRIX 1）+ `max7219_write_digit(digit, value)` / `max7219_write_matrix(rows, matrices1-4)` + `max7219_write_reg(chip, addr, data)` / `max7219_clear()` / `max7219_set_chip_count(count)`。

**关键事实（%TEMP%\batch10-facts.md）：** 两页全 F1，**页内自洽**（数码管 BCD 译码无字模表；点阵字模表 disp1[12][8] 页内 L383-408——演示数据不放? mspm0 先例：演示字模不入库（batch3）——页面 disp1 是演示字模 → 不入库，notes）；页面默认脚（PB9/PB18 等 mspm0 板脚）不照抄；**用移位指令写寄存器时序（页面原式）**。

**引脚与默认脚（互替同脚先例）：**
- pins：`MAX7219_DIN`（gpio_out，default **PC13**）/ `MAX7219_CLK`（gpio_out，default **PC14**）/ `MAX7219_CS`（gpio_out，default **PC15**），macros 6 个（`MAX7219_DIN_GPIO/_DIN_PIN` 等）。
- pin_config.h：`#define MAX7219_DIN_GPIO GPIO_C`/`_DIN_PIN Pin_13`、CLK Pin_14、CS Pin_15（注释：默认叠板载 LED 三灯（PC13-15）——**显示替代指示**（有数码管/点阵就不用板载灯，互替同脚先例 ttp224×key_matrix）；三脚同口；与 lcd/oled 屏互替；同选经绑定消解）。

**被谁阻塞：** 无——可立即开始（本批打样件）。

**状态：** resolved（2026-09 实施完成）。

**实施清单：**
- [x] `library/modules/max7219/code/max7219_stm32.c/.h`（独立 stm32 头——API 6 函数照 mspm0 max7219.h；.c 软 SPI 移位（gpio_set + 位序 MSB 先——照 mspm0 .c 逐行）；零引脚字面量）
- [x] manifest.json platforms 增 stm32：files `[code/max7219_stm32.c, code/max7219_stm32.h]`、dependencies ["delay"]（照 mspm0 现状）、verified false、hardware_bound false、pins 3 行、kit/source_url（wiki 原页 `.../screen/8-bit-led-tube.html`——另一页 max7219-matrix-display 同 slug 记 notes）、notes（手册路径×2+原页+网盘+**两页合一（同芯片双形态）**+演示字模不入库+默认脚推理（LED 三灯互替）+未上板）
- [x] pin_config.h 增 6 宏
- [x] 测试 `tests/test_module_max7219.py`：形状（3 pins）+宏存在（`MAX7219_DIN_GPIO\s+GPIO_C` 等）+单选生成+mspm0 零改动+守卫（`FORM_DIGIT 0u`/`FORM_MATRIX 1u`、`0x09`/`0x0F` 寄存器、无演示字模数组、无 printf/GPIO_Init/RCC_）
- [x] test_pins.py 补 6 宏；test_default_layout.py 白名单 PC13-15 组 +3
- [x] UV4 矩阵（init(0,2)+write_digit(0,1)+write_matrix(0,0,0,0,0)+write_reg(0,0x0F,0)+clear+set_chip_count(1) 全调，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论（2026-09 实施完成）**：stm32 条目落地——code/max7219_stm32.c/.h（软 SPI 3 脚 gpio_set 位操作 + 页原式 OUT_PP；API 6 函数与 mspm0 版同名同型完全对齐）；默认脚 DIN=PC13/CLK=PC14/CS=PC15（叠板载 LED 三灯——显示件与板载指示灯输出指示互替）；manifest platforms.stm32（files 2 件、deps 无（无 delay 调用——照 mspm0 现状）、3 pins、kit/source_url 8-bit-led-tube 页、notes 两页合一 + 演示字模不入库 + 未上板）；pin_config.h 6 宏 + test_pins 钉值 + test_default_layout 白名单（PC13-15 组）；测试 test_module_max7219.py stm32 段全绿；UV4 矩阵 0 error/0 warning → verified=true（.scratch/wiki-stm32-batch10/matrix/run_max7219_matrix.py——Code=1868）；wordlist 零补录复核（已挂接）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
