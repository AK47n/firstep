# 05 — lcd 补 ST7735S（1.8 寸 128×160，触摸解耦）

**要做什么：** `lcd` 模块补 `LCD_MODEL_180`（1.8 寸，厂家目录 中景园ZJY180S120TTG01技术资料\02-1.8LCD带触摸程序源码.zip，C8T6 带触摸例程）：ST7735S 初始化序列 + 分辨率 128×160 / 160×128 + 偏移表（厂家 lcd_init.c——0.96 也是 ST7735 系但面板不同，序列/偏移不同，**勿与 LCD_MODEL_096 混用**，逐字核对）。**本件不收触摸**（XPT2046 由工单 06 独立件承载——spec 决策 A，lcd 模块零触摸耦合）；notes 说明 1.8 屏触摸 = 选 lib 内 tp_xpt2046 配套、接线（触摸与 LCD 共用 SCLK/MOSI + 独立 CS）按绑定自由度。同构管线（测试更新 + 矩阵重跑 + notes 补 screen--1-8-touch-color-screen.md）。

**被谁阻塞：** 01。

**状态：** pending

**验收：**

- [ ] lcd_init.c 补 ST7735S model 表项（128×160；与 096 的序列/偏移差异逐字核对并 notes 记录）
- [ ] lcd.h LCD_MODEL_180 常量；测试断言更新；font 无变化
- [ ] manifest notes 补 1.8 页信息（wiki 页路径+原页+网盘+厂家目录+触摸解耦说明）
- [ ] 编译矩阵重跑 PASS；中文提交、工单 resolved
