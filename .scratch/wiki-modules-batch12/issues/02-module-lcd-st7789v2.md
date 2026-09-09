# 02 — lcd 补 ST7789V2（1.3 寸 240×240 带字库版 + 1.69 寸 240×280）

**要做什么：** `lcd` 模块补 `LCD_MODEL_130`（1.3 寸，厂家目录 中景园ZJY130S10Z0TG01技术资料\02-1.3IPS带字库程序源码.zip，C8T6 带字库例程 HARDWARE\LCD\）与 `LCD_MODEL_169`（1.69 寸，中景园ZJY169S0800TG01技术资料\03-程序源码.zip，C8T6 例程）两条 model 表项：初始化序列（ST7789V2）+ 分辨率（240×240 / 240×280）+ 偏移表 + 默认方向（1.3 竖 0 / 1.69 竖 0）。**核对字库策略**：1.3 带字库版的 `zk.c`（外置 SPI 字库芯片）不并入——spec 决策 A 已定，lcd 汉字能力 = 内嵌 16x16 常用集（与 01 同一份 lcdfont.h，无变化）；两屏仅 lcd_init 序列/偏移表差异（厂家 lcd.c/字库字节级一致——已 MD5 核实）。补测试断言（新 model 常量 + 分辨率表项 + 单选生成仍是同一 LCD 实例零 syscfg 变化）；编译矩阵重跑（0 error/0 warning）；manifest notes 补两页（wiki 页路径+原页+网盘链接+厂家目录路径）。

**被谁阻塞：** 01（lcd 模块与管线基建先立）。

**状态：** resolved

**结论：** 2026-09-12 完成并提交（e346776a）。lcd_init.c 新增 lcd_seq_130/lcd_seq_169（ST7789V2 双型号——1.3 寸 240×240 带字库版 + 1.69 寸 240×280；厂家初始化序列原样录入——1.3 双 0x11 Sleep out 各延时 120ms + E0/E1 13 字节 gamma + E4 240 gate；1.69 E0/E1 13 字节；0x36 MADCTL 藏占位按方向替换）+ lcd_models 表项（130：全方向 240×240、madctl {00,C0,70,A0}、dir1/3 行/列 +80 偏移、默认方向 0；169：竖 240×280 横 280×240、dir0/1 行 +20、dir2/3 列 +20、默认方向 0——厂家 Address_Set 方向表原样）；字库核对：1.3 带字库版 = 外置 SPI 字库芯片（zk.c）不入库——汉字能力内嵌 tfont16 常用集（决策 A）；manifest notes 补 1.3/1.69 两页（原页/网盘 8888/软件 SPI v9i7、6lhw/厂家目录 zip）；测试更新 + 矩阵 PASS（0 error/0 warning）；未上板。

**验收：**

- [x] lcd_init.c 补 ST7789V2 双 model 表项（1.3 = 240×240、1.69 = 240×280，各带偏移表与方向表；序列从厂家 lcd_init.c 提炼）
- [x] lcd.h LCD_MODEL_130/169 常量；test_module_lcd.py 型号完整性断言更新（6 模型常量最终齐）
- [x] manifest notes 补两页信息（screen--1-3-color-screen.md / screen--1-69-color-screen.md + 网盘链接 + 厂家目录 + 字库芯片不入库决策记录）
- [x] 编译矩阵重跑 PASS（0 error/0 warning）→ verified 保持 true、notes 补记录；中文提交、工单 resolved


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
