# 批次 10「显示件组」— 立创 wiki 地阔星 STM32F103C8T6 手册模块批量入库（stm32 线）

## 问题陈述

stm32 线进度：批次 1-9 已入库 58 件。本批 = **显示件组**：max7219（数码管+点阵 2 页 1 件）、lcd（五篇彩屏六合一——stm32 新实现）、tp_xpt2046（1.8 触摸）、oled 变体补缺口（0.96 SPI / 0.91 128×32 / 1.3 SH1106——**C 类**：stm32 侧 ml_oled 仅 I2C 128×64，SPI/分辨率/SH1106 无实现）+ **B 类 ili9341/ili9488**（新 slug——**需用户下载 lcdwiki 例程包**，工单 06/07 待资料）。

**关键利好（页内自洽审计结论）**：五篇彩屏/1.8 触摸/单色 OLED 页内虽缺字库，但 **mspm0 线已把完整实现入库**（lcdfont.h 15.9KB、oledfont.h 37.8KB、lcd_models[6] 表、XPT2046 驱动）——stm32 版直接复用库内字库与结构，**零下载**；仅 ilit9341/ili9488（库内无对照 + 页内零驱动）需用户下载 lcdwiki 包。

## 方案

照批次 1-9 管线。显示件 = 软 SPI 位操作（不占硬件 SPI——母版无 ml_spi；零 TIMER）+ 复用库内 mspm0 字库/绘制结构（换算 ml_* 总线 API）。oled 变体：stm32 侧 oled 模块 files 从 [] 增补 `code/oled_extra_stm32.c/.h`（SPI 总线 + 0.91/SH1106 变体——I2C 仍内嵌 ml_oled；照 mspm0 批 12/07 决策 B「同芯片同 API 仅总线层」）。每件：提炼换算 → pin_config.h 宏段 → manifest → 测试 → UV4 矩阵 0/0 → verified → 中文提交。

## 用户故事

1. 做题用户选 stm32 + max7219：`max7219_init(form,brightness)/write_digit/write_matrix/clear` 直接驱动数码管/点阵。
2. 做题用户选 stm32 + lcd：`lcd_init(model,dir)/lcd_show_string/lcd_fill` 等（六屏合一 + 库内字库）——显示不再「需自备」。
3. 做题用户选 stm32 + oled：`OLED_SPI_Init()/oled_set_res(128X32)/oled_show_text` 等（SPI/0.91/SH1106 变体齐，I2C 原有）。
4. 做题用户选 stm32 + tp_xpt2046：`xpt2046_init/read_xy/is_pressed` 触摸。
5. 做题用户选 stm32 + ili9341/ili9488（资料到手后）：大屏 320×240/480 新模块。
6. 维护者：每件可溯源（A 类 source_url；B 类 notes 口径 + 资料来源）。

## 实现决策

### 既定事实（勿重新调研；batch10-facts.md 已取证）

① **F4 混写甄别（3 页）**：0-96-single-spi / 0-96-color / 1-47-color 三页**仅软 SPI 初始化块为 F4 语法**（RCC_AHB1PeriphClockCmd + GPIO_Mode_OUT + OType_PP + PuPd——L96-103/L100-112/L127-134），其余（硬 SPI 块/其余代码）全 F1——提炼时软 SPI 块改写 F1（RCC_APB2PeriphClockCmd + GPIO_Mode_Out_PP + GPIO_Speed_50MHz）。
② **字库/驱动复用（mspm0 已入库）**：lcdfont.h 15.9KB（1206/1608 ASCII + tfont16 汉字）、oledfont.h 37.8KB、lcd_init.c `lcd_models[6]` 表（序列+分辨率+偏移+MADCTL）——stm32 版直接复用（**拷贝进 stm32 files 或共享**：mspm0 files = lcd.c/lcd.h/lcd_init.c/lcd_init.h/lcdfont.h——stm32 条目 files 照抄同目录文件名（code/ 同目录, mspm0 与 stm32 共用同一份文件——**双平台共享文件先例 filter.c** ✓）。
③ **oled 变体补缺口（C 类口径）**：stm32 侧 oled files 从 [] → `[code/oled_extra_stm32.c, code/oled_extra_stm32.h]`（新增——I2C 仍内嵌 ml_oled）；内容 = `oled_spi_init()`（软 SPI 5 脚——照 mspm0 OLED_SPI_Init 决策 B 结构）+ `oled_set_res(OLED_RES_128X32)`（0.91——须 init 前，mspm0 核验值 MUX 0x1F/COM 0x00）+ SH1106 变体（**专属序列 0xAD/0x8B/0x33/列偏移 0x02 页内完整 L116-142——A 类直提**；API = `oled_sh1106_init()` 或 oled_set_res 变体宏——照 mspm0 无 SH1106 提炼先例 → 新 API 设计：`oled_init_sh1106()`）；字库复用 oledfont.h（母版 ml_oled 已含）；**0-96-iic 页 = 纯核对**（库已支持 128×64 I2C——批 11 核对）。
④ **软件 SPI 组与互替同脚**：显示族互替（一次选一块屏）——lcd 六脚组 / oled SPI 五脚组 / max7219 三脚组 **组内互替同脚**（lcd×oled 大屏小屏互替、max7219×两者互替——同脚先例 ttp224×key_matrix；**tp 与 lcd 为配套件（1.8 触摸=屏+触同选）刻意错开**——mspm0 批 12 同款）。
⑤ **默认脚拍板**（低同框推理 + 白名单登记 + 实施微调 notes；脚位紧张为常态）：
   - **max7219（3 脚）**：DIN=PC13 / CLK=PC14 / CS=PC15——叠板载 LED 三灯（**显示替代指示——有数码管就不用板载灯**，互替同脚先例；三脚同口）
   - **lcd（6 脚）**：SCL=PB4 / SDA=PB5 / RES=PA5 / DC=PB6 / CS=PB7 / BLK=PA15——叠继电器+编码器方向（PB4）/称重+旋钮+编码器（PB5）/火焰+ADC 组（PA5——屏×火焰不同框）/舵机+巡线（PB6）/人体红外（PB7）/蜂鸣（PA15）
   - **oled SPI（5 脚，与 lcd 组互替同脚——大屏/小屏互替一次选一）**：SCL=PB4 / SDA=PB5 / DC=PB6 / CS=PB7 / RES=PA5（lcd 组子集）
   - **SH1106 变体（同 oled 组同脚）**
   - **tp_xpt2046（5 脚，配套 lcd 刻意错开）**：CS=PB12 / CLK=PB13 / DIN=PB14 / DOUT=PB15 / PEN=PB0——叠 DIP+GRAY+触摸（ttp224 互替同脚）+称重/旋钮/测温（PEN）
   - **ili9341/ili9488（待资料）**：默认脚 = lcd 六脚组同款（ILI 屏×中景园屏互替）+ 触摸复用 tp 组——资料到位后按包内 lcd.h 引脚宏核对（**页内连引脚宏定义表都没有——默认脚只能从包内取**）。
⑥ **mspm0 API（stm32 命名对齐目标，工单逐函数照搬）**：max7219（init(form,brightness)/write_digit/write_matrix/write_reg/clear/set_chip_count——FORM_DIGIT 0/MATRIX 1）；lcd（init(model,dir)/get_width/height/fill/clear/draw_point/line/rectangle/circle/show_char/string/num/float/chinese16x16/picture——LCD_MODEL_096/128/130/147/169/180）；oled（OLED_Init 内嵌/OLED_SPI_Init/oled_set_res/oled_show_* 双平台小写族——照 mspm0 oled.h）；tp_xpt2046（init/set_calibration/read_raw/read_xy/is_pressed）。
⑦ **B 类设计**（ili9341/ili9488）：新 slug 独立（库内 lcd 六合一不含 ILI 系——差异=序列+分辨率+16bit 像素）；构件壳照 lcd 模式（`ili9341_init(dir)` + 通用绘制/文本 API 照 mspm0 lcd.h 风格——不照 lcdwiki 旧壳 lcddev/POINT_COLOR）；初始化序列取自 lcdwiki 包（页内零序列）；触摸复用 tp_xpt2046（同芯 XPT2046——lcdwiki 位带宏 PAin/PAout 换算 ml_gpio，不引入 sys.h）；字库复用库内 lcdfont.h；性能风险（软 SPI 320×240 全屏 ≈0.27s——notes：建议局部刷新，硬 SPI 方案范围外）；GUI/test.c 归骨架（ADR 0009）。

## 测试决策

- `tests/test_module_max7219.py` / `test_module_lcd.py` / `test_module_tp_xpt2046.py` / `test_module_oled_extra.py`（oled 变体——照 mspm0 批 12/07 测试对仗：I2C 路径零变化断言 + SPI 变体测试）：
  - 形状（files 含共享 lcdfont.h 等——双平台共享先例）+ 宏存在（PIN 宏族）+ 单选生成全流程 + mspm0 零改动守卫 + 守卫（max7219 `0x09`/`0x0F` 寄存器族、FORM_DIGIT/MATRIX；lcd `LCD_MODEL_096`..`LCD_MODEL_180`、`0x3C`/`0x36`/`0xA1` 序、字库 lcdfont.h 体积 ≤16KB 断言（mspm0 先例）；tp 5 次中值滤波、PEN 轮询无中断；oled extra：SPI 总线函数 + `OLED_RES_128X32` + SH1106 `0xAD`/`0x8B`/`0x33` 序列 + 列偏移 `0x02` + I2C 既有路径零变化）。
- `tests/test_pins.py` STM32_MACRO_VALUES 补宏（六组约 30 宏）；test_default_layout.py 白名单（PC13-15 组 +3、PB4/5/6/7 +4、PA5 +1、PA15 +1、PB12-15 组 +4、PB0 +1——显示组登记）。
- UV4 矩阵（每件照配方；lcd 矩阵 MAIN_C 调 init(model)+show_string+fill+draw_point 等全部 API (void) 化；oled 矩阵含 I2C+SPI 双路径）→ 0/0 → verified=true。
- **ili9341/ili9488 测试**：资料到位后补（B 类模板——与批 10 收尾）。词表：max7219/lcd/oled/tp 已挂接零补录；ili9341/ili9488 资料到位后补录。

## 范围外

- ili9341/ili9488 实施（待用户下载 lcdwiki 包——工单 06/07 blocked）；1.14 寸（st7789_para——批 11 收官与 vl53l0x 一起）；0-96-iic 纯核对（批 11）；mspm0 条目改动（零改动——oled files 增补仅 stm32 侧）；上板真机验证（notes——软 SPI 时序/刷屏性能/触摸校准真机留后续）。
- 硬 SPI（新增 ml_spi——母版功库改动范围外；性能 note 保留）；pic.h 演示位图（mspm0 先例不入库）；zk.c/zk.h 板载字库 ROM（按 mspm0 口径不并入——汉字走 lcdfont.h tfont16）；lcdwiki 的 GUI/test.c 演示（归骨架）。
- SH1106 与 SSD1306 像素细节差异（1.3 屏 128×64——列偏移 0x02 页内完整；真机验证留后续）。

## 补充说明

- 排序：01 max7219（3 脚打样）→ 02 lcd（六屏合一最重）→ 03 tp_xpt2046 → 04 oled SPI+0.91 变体 → 05 oled SH1106 变体 → 06 ili9341（待资料）→ 07 ili9488（待资料）。
- 页内事实 = %TEMP%\batch10-facts.md（7a46b84e 报告，2026-09 回填）。
- 收尾清单：全量测试 → sweep 更新 → code-review 两轴 → CONTEXT 补录 → 中文提交（ili 两件资料到位后单件收尾——与 vl53l0x 同款）。
