# 06 — ili9341 大屏彩屏（B 类新 slug · 仅 stm32 · 待 lcdwiki 资料，手册 screen--2-8-and-3-2-color-sreen.md）

**要做什么：** 模块库新增 **`ili9341`**（库内无此模块——B 类，**仅 stm32 平台条目**）：从 lcdwiki MSP2807 例程包（页面 L12 链接）+ 页面提炼 ILI9341 320×240 16bit 驱动为纯驱动切片（软 SPI 6 脚 + 触摸复用 tp_xpt2046），API 照 mspm0 lcd.h 风格（`ili9341_init(dir)` + `ili9341_fill/clear/draw_point/line/show_string/show_num/...`——**不照 lcdwiki 旧壳** lcddev/POINT_COLOR/LCD_ShowString(带 fc/bc)）。**状态：待资料（blocked）**。

**为什么待资料（已取证，%TEMP%\batch10-facts.md）：** 页面 F1 但**真·全页外**——页内零驱动（连初始化序列都没有），只有 lcdwiki MSP2807 例程包链接（L12）+ 效果图百度盘（L376）；**页内连引脚宏定义表都没有**（默认脚必须从包内 lcd.h 取）；触摸 XPT2046 与 tp_xpt2046 同芯可复用。

**✅ 资料已到位（2026-09，用户解压）**：`sources/materials/lckfb-地阔星移植手册/网盘下载/ili9341/2.8inch_SPI_Module_ILI9341_MSP2807_V1.1/`（36.5MB）——含 `1-Demo/Demo_STM32/Demo_STM32F103RCT6_Hardware_SPI/`（**硬件 SPI 版**例程：HARDWARE/LCD/lcd.c+lcd.h+FONT.H、TOUCH/touch.c、SPI/SPI.c）+ `4-Driver_IC_Data_Sheet/ILI9341 Datasheet.pdf` + 用户手册/原理图 + `6-User_Manual/STM32_Keil_Use_Illustration_CN.pdf`；**引脚宏表在 HARDWARE/LCD/lcd.h**。注意：**例程为硬件 SPI 版**——实现时按**软 SPI 位操作**换算（批 8 nrf24l01/rc522 先例），SPI.c 仅作时序/初始化参考；**FONT.H 是 lcdwiki 自带字库——按 mspm0 口径复用库内 lcdfont.h（1206/1608+tfont16），FONT.H 作对照参考不整包入库**（GBK 大字号不入库，notes）。

**被谁阻塞：** ~~用户下载 lcdwiki 包~~ **资料已到位——可立即开始**（与工单 07 同批）。

**状态：** resolved（2026-09 实施完成）。

**实施清单（资料已到位——可直接开工）：**
- [x] 读包内 `HARDWARE/LCD/lcd.c/lcd.h`（**软 SPI 换算**——硬件 SPI 版例程的 SPI.c 仅时序参考；**引脚宏表从 lcd.h 取默认脚**）→ 提炼（初始化序列/绘制 API）→ 纯驱动切片（去 main/printf、API 照 mspm0 lcd.h 风格命名）→ 软 SPI 换算（gpio_set 位操作宏族）→ 字库复用库内 lcdfont.h（1206/1608+tfont16——**FONT.H 不入库**，GBK 大字号演示不入库）；触摸 XPT2046 复用 tp_xpt2046 模块（同芯）
- [x] `library/modules/ili9341/`：code/ili9341_stm32.c/.h（API 照 mspm0 lcd.h 风格——工单 02 的 lcd API 为准实施）| manifest.json（**仅 platforms.stm32**：files、pins（软 SPI 六脚默认 = **lcd 六脚组同款**（ILI 屏×中景园屏互替同脚）+ 触摸 pins（复用 tp 组——互替同脚））、verified 初 false、kit/source_url（wiki 原页 + **lcdwiki 官网链接**（notes——双来源）、notes（B 类口径+下载来源+序列/引脚取自 lcdwiki 包+位带换算记录+触摸复用+性能风险（软 SPI 全屏 ≈0.27s——建议局部刷新）+未上板）+ description（能力方向：大屏显示/ILI9341；无题绑定）
- [x] pin_config.h 宏段（按包内 lcd.h 引脚表——**资料到位后核对**）
- [x] 测试 test_module_ili9341.py（B 类模板：仅平台/形状/单选生成/守卫——序列关键字节/无 lcdwiki 旧壳名（`POINT_COLOR`/`LCD_ShowString` 不得出现）/无 sys.h 位带）
- [x] UV4 矩阵 0/0 → verified=true
- [x] wordlist 补录（显示模块 + models + lib_modules）
- [x] 中文提交 → resolved → 结论回填（资料来源/引脚表/序列要点）

**结论（2026-09 实施完成）**：B 类新 slug 落地——library/modules/ili9341/（code/ili9341_stm32.c/.h + code/ili9341_font.h（lcdfont.h 同源副本——头基名全局唯一门禁改名 + 数组 static 化防双选链接重复））；初始化序列/MADCTL 方向表（0x08/0x68/0xC8/0xA8）/18bit 参数全取自 lcdwiki MSP2807 包（F103 软 SPI 版——页面链接原标硬件 SPI 版，包内另含软 SPI 版，实施以软 SPI 版为准记录）；API 照 mspm0 lcd.h 风格（不照 lcdwiki 旧壳：lcddev/POINT_COLOR/LCD_ShowString 弃用）；默认脚 = lcd 六脚组同款（ILI 屏×中景园屏互替同脚）；触摸复用 tp_xpt2046（同芯——配套件零耦合）；pin_config.h 12 宏 + 测试全绿（序列字节/无旧壳/无位带宏/字库 ≤17KB 副本预算）；UV4 矩阵 0 error/0 warning → verified=true（run_ili9341_matrix.py——Code=4624/RO=3104）；wordlist 显示模块组补录（2.8/3.2/3.5 寸 ILI 大屏方案 + models ILI9341/ILI9488）；页面零驱动/零引脚表（全页外）记录。

**验收标准：** 资料下载 → 实施 → 全部 checkbox；pytest 绿；矩阵 exit 0。资料未到 = 保持待资料，不阻塞批次 10 其余件收尾。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
