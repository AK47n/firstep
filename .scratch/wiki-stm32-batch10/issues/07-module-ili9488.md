# 07 — ili9488 大屏彩屏（B 类新 slug · 仅 stm32 · 待 lcdwiki 资料，手册 screen--3-5-ili9488-color-screen.md）

**要做什么：** 模块库新增 **`ili9488`**（库内无此模块——B 类，**仅 stm32 平台条目**）：从 lcdwiki MSP3520 例程包（页面 L12 链接）+ 页面提炼 ILI9488 320×480 16bit 驱动为纯驱动切片（软 SPI 6 脚 + 触摸复用 tp_xpt2046；**ILI9488 的 18bit 面板 16bit 打包方式只能按包内实现**——页面零序列零引脚表）。API 照 mspm0 lcd.h 风格（`ili9488_init(dir)` + 绘制/文本 API 族——同工单 06 规范）。**状态：待资料（blocked）**。

**为什么待资料（已取证，%TEMP%\batch10-facts.md）：** F1 页面**真·全页外**（驱动全缺、初始化序列无、**页内连引脚宏定义表都没有（只有宏名）——默认脚只能从包内 lcd.h 取**）；lcdwiki MSP3520 包链接 L12（`http://www.lcdwiki.com/zh/3.5inch_SPI_Module_ILI9488_SKU:MSP3520`）+ 效果图百度盘 L277；触摸 XPT2046 同芯复用。

**✅ 资料已到位（2026-09，用户解压）**：`sources/materials/lckfb-地阔星移植手册/网盘下载/ili9488/3.5inch_SPI_Module_ILI9488_MSP3520_V1.1/`（42.6MB）——含 **`1-Demo/Demo_STM32/Demo_STM32F103RCT6_Software_SPI/`（软 SPI 版例程——直接匹配母版无 ml_spi 约束：HARDWARE/LCD/lcd.c+lcd.h+FONT.H、TOUCH/touch.c、USER/GUI.pic.test、SYSTEM/sys）** + `Hardware_SPI` 版对照 + `4-Driver_IC_Data_Sheet/ILI9488 Data Sheet.pdf` + 原理图/用户手册/取模工具；**引脚宏表在软 SPI 版 HARDWARE/LCD/lcd.h + SYSTEM/sys/sys.h（位带宏——换算 ml_gpio 不引入 sys.h）**。

**被谁阻塞：** ~~用户下载 lcdwiki 包~~ **资料已到位——可立即开始**（与工单 06 同批）。

**状态：** resolved（2026-09 实施完成）。

**实施清单（资料已到位——可直接开工，同工单 06 规范）：**
- [ ] 读软 SPI 版 `HARDWARE/LCD/lcd.c/lcd.h`（**初始序列 + 18bit 面板 16bit 打包**——包内实现为准；**引脚宏表 lcd.h 取默认脚**；sys.h 位带宏换算 ml_gpio 不引入）→ 纯驱动切片（API 照 mspm0 lcd.h 风格；**不引入 lcdwiki 旧壳**）→ 软 SPI 换算 → 字库复用 lcdfont.h（FONT.H 不入库）；触摸复用 tp_xpt2046（同芯 XPT2046）
- [ ] `library/modules/ili9488/`：code/ili9488_stm32.c/.h + manifest.json（仅 platforms.stm32：files、pins（**默认六脚 = lcd 组同款互替 + 触摸 tp 组**）、verified 初 false、kit/source_url（wiki 原页 + lcdwiki 官网链接——notes 双来源）、notes（B 类口径+下载来源+**18bit 打包/引脚表取自包内**+位带换算+性能风险（全屏 ≈0.55s——局部刷新建议）+未上板）、description（能力方向：大屏显示/ILI9488；无题绑定）
- [ ] pin_config.h 宏段（包内 lcd.h 引脚表核对）
- [ ] 测试 test_module_ili9488.py（B 类模板 + 守卫：序列关键字节/18bit 打包/无 POINT_COLOR/LCD_ShowString/sys.h）
- [ ] UV4 矩阵 0/0 → verified=true
- [ ] wordlist 补录
- [ ] 中文提交 → resolved → 结论回填

**结论（2026-09 实施完成）**：B 类新 slug 落地——library/modules/ili9488/（code/ili9488_stm32.c/.h + code/ili9488_font.h（同 ili9341 副本口径））；**18bit 面板 16bit 打包**（0x3A 0x66 + 每像素 3 字节流 RED 0xF8/GREEN 0xFC/BLUE <<3——包内原式直提）；初始化序列全取自 lcdwiki MSP3520 软 SPI 版包；API 照 mspm0 lcd.h 风格（ili9488_ 前缀全族——与 ili9341 同构）；默认脚 = lcd 六脚组同款（互替同脚）；触摸复用 tp_xpt2046；pin_config.h 12 宏 + 测试全绿（18bit 打包守卫/无旧壳/无位带宏/字库预算）；UV4 矩阵 0 error/0 warning → verified=true（run_ili9488_matrix.py——Code=4500/RO=3104）；性能 notes（全屏 ≈0.55s——18bit 3 字节/像素）；wordlist 补录同工单 06（ILI 大屏方案合一条 + models）。

**验收标准：** 同工单 06（资料到位后实施；期间不阻塞批次收尾）。
