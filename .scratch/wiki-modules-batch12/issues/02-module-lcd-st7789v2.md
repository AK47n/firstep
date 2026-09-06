# 02 — lcd 补 ST7789V2（1.3 寸 240×240 带字库版 + 1.69 寸 240×280）

**要做什么：** `lcd` 模块补 `LCD_MODEL_130`（1.3 寸，厂家目录 中景园ZJY130S10Z0TG01技术资料\02-1.3IPS带字库程序源码.zip，C8T6 带字库例程 HARDWARE\LCD\）与 `LCD_MODEL_169`（1.69 寸，中景园ZJY169S0800TG01技术资料\03-程序源码.zip，C8T6 例程）两条 model 表项：初始化序列（ST7789V2）+ 分辨率（240×240 / 240×280）+ 偏移表 + 默认方向（1.3 竖 0 / 1.69 竖 0）。**核对字库策略**：1.3 带字库版的 `zk.c`（外置 SPI 字库芯片）不并入——spec 决策 A 已定，lcd 汉字能力 = 内嵌 16x16 常用集（与 01 同一份 lcdfont.h，无变化）；两屏仅 lcd_init 序列/偏移表差异（厂家 lcd.c/字库字节级一致——已 MD5 核实）。补测试断言（新 model 常量 + 分辨率表项 + 单选生成仍是同一 LCD 实例零 syscfg 变化）；编译矩阵重跑（0 error/0 warning）；manifest notes 补两页（wiki 页路径+原页+网盘链接+厂家目录路径）。

**被谁阻塞：** 01（lcd 模块与管线基建先立）。

**状态：** pending

**验收：**

- [ ] lcd_init.c 补 ST7789V2 双 model 表项（1.3 = 240×240、1.69 = 240×280，各带偏移表与方向表；序列从厂家 lcd_init.c 提炼）
- [ ] lcd.h LCD_MODEL_130/169 常量；test_module_lcd.py 型号完整性断言更新（6 模型常量最终齐）
- [ ] manifest notes 补两页信息（screen--1-3-color-screen.md / screen--1-69-color-screen.md + 网盘链接 + 厂家目录 + 字库芯片不入库决策记录）
- [ ] 编译矩阵重跑 PASS（0 error/0 warning）→ verified 保持 true、notes 补记录；中文提交、工单 resolved
