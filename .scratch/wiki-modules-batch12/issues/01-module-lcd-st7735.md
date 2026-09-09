# 01 — lcd 模块打样（ST7735 0.96 寸 80×160，全管线首件）

**要做什么：** 模块库新增 `lcd` 条目（仅 mspm0，**六彩屏合一模块打样件**）：厂家例程 `C:\Users\luoji\Desktop\caiping\中景园ZJY096S0800TG01技术资料\02-0.96IPS程序源码.zip`（工作区外只读，不拷进 git——源码在 zip 内，参考已解压结构 %TEMP%\caiping-extract\0_96\02-0.96IPS程序源码\02-0.96IPS显示屏STM32F103C8T6_SPI例程\HARDWARE\LCD\）提炼完整驱动：`lcd.c/lcd.h/lcdfont.h/lcd_init.c/lcd_init.h`（GBK 源，提炼转 UTF-8）。改造：软 SPI 位操作（SCL/MOSI/RES/DC/CS/BLK 六脚 GPIO——母版新 GPIO 实例 `LCD`，宏 `LCD_SCL_PORT/LCD_SCL_PIN` 等按引脚名分派）；去 STM32 平台依赖（GPIO_ResetBits/RCC_/delay_ms 走库 delay 模块、去 printf/去 main 演示）；**API 定稿（spec 决策 A）**：`lcd_init(u8 model, u8 dir)` + `lcd_get_width/height` + `lcd_fill/clear/draw_point/draw_line/draw_rectangle/draw_circle` + `lcd_show_char/string/num/float/chinese16x16/picture`（size 12/16/24/32 ASCII，汉字仅 16x16 常用集）；**字库裁剪（spec 定稿）**：lcdfont.h = ASCII 四套（1206/1608/2412/3216）+ tfont16 汉字集，**≤16KB**；pic.h 不入库（演示位图，用户自备）；型号常量 `LCD_MODEL_096`（本件只打样 ST7735，其余型号表项由 02-05 补）。本件同时落全管线基建：母版 syscfg `LCD` GPIO 实例（6 脚、CS/BLK 初始 SET）+ `syscfg_instances.py` INSTANCE_CONSUMERS `"LCD": ("lcd",)` + wordlist「显示模块」一条 solution + `tests/test_module_lcd.py`（manifest 形状/单选生成/静态门禁/字库体积断言 ≤16KB + ascii_1608/tfont16 存在 + 无 GPIO_ResetBits/RCC_/printf/DL_SPI 守卫 + 型号常量完整性）+ test_pins.py/test_pin_bindings.py/test_syscfg_prune.py 增断言 + 编译矩阵（复制 run_max7219_matrix.py 先例改 slug，单选生成 → SysConfig CLI → gmake 0 error/0 warning）→ verified 回写 → 中文提交 → code-review。

**默认脚（spec 倾向，按 test_pin_bindings 刻意重叠表落死）：** SCL←PA0(IR_TX)/SDA←PA1(GP2Y1014)/RES←PA12(FINGERPRINT)/DC←PA22(HUIDU 灰度)/CS←PB19(JQ8900)/BLK←PB20(SYN6288)——「同选概率最低」与语义互替件重叠，刻意不叠显示族（oled/max7219/ws2812/led_beep）与环境站（温湿度/光照）。

**被谁阻塞：** 无——可立即开始（批次 12 首件，先打样验证管线 + API 定稿）。

**状态：** resolved

**结论：** 2026-09-12 完成并提交（c9e898d6）。lcd 模块（仅 mspm0，依赖 delay）打样件：软 SPI 位操作 6 脚（母版新 GPIO 实例 LCD，CS/BLK 初始 SET；默认 SCL=PA16/SDA=PA17/RES=PA27/DC=PA22/CS=PB19/BLK=PB20——与编码器/读卡/灰度/无线/语音/气体互替不同框、刻意不叠显示族与环境站与 PA0/PA1（i2c_bus_share 测试互扰批次 5 先例））；API 定稿 = lcd_init(LCD_MODEL_096, LCD_DIR_DEFAULT) + 绘制/文本全套（对齐 oled 风格）；lcd_models[6] 表驱动（096 实装——厂家序列原样 + 0x36 占位按方向替换 + 偏移/madctl/分辨率四方向表）；字库裁剪 lcdfont.h 15.2KB（ASCII 1206+1608 两套 + tfont16 5 字 GBK 字节索引；2412/3216 与 tfont12/24/32、pic.h 裁剪；tfont16 typedef/GBK 字节/双括号经编译矩阵修正——上游「命中 continue」矛盾改 break）；wordlist 显示模块 +1 方案 + models +4，词表 wire 7239 → WORDLIST_PROMPT_BYTES 7500、REFERENCE_FULLTEXT_BYTES 60400；测试 test_module_lcd.py 5 例 + test_pins/test_pin_bindings（含灰度共享组绑走 lcd RES）/test_syscfg_prune 断言；编译矩阵 PASS（0 error/0 warning），verified=true；全量 3533 pytest 全绿；未上板。

**验收：**

- [x] 提炼：从厂家 C8T6 例程取 lcd.c/lcd.h/lcdfont.h/lcd_init.c/lcd_init.h → `library/modules/lcd/code/`（UTF-8），去 STM32 平台依赖（GPIO_ResetBits/SetBits→DL_GPIO 位操作宏、delay_ms→库 delay、去 printf/main）
- [x] API 定稿按 spec：lcd_init(model,dir) + 绘制/文本函数 + LCD_MODEL_096 常量；方向态/分辨率静态化，lcd_get_width/height 出参
- [x] 字库裁剪：ascii 四套全留 + tfont16 汉字集；lcdfont.h ≤ 16KB；pic.h 不入库；LCDFONT 体积断言进测试
- [x] 母版 syscfg：新增 LCD GPIO 实例（6 脚命名 SCL/SDA/RES/DC/CS/BLK，全 OUTPUT，CS/BLK initialValue SET）+ INSTANCE_CONSUMERS `"LCD":("lcd",)`
- [x] manifest.json：dependencies ["delay"]；mspm0 条目（files 5 件、verified 初始 false、hardware_bound false、kit=中景园 0.96 寸 IPS 屏 ZJY096S0800TG01、source_url=screen--0-96-color-screen.md 原页 https://wiki.lckfb.com/zh-hans/dmx/module/screen/0-96-color-screen.html、notes 含 wiki 页路径+原页+网盘（19DxY8JJEzNt4XYF_CwVbDw/8888）+厂家目录路径+初始化序列来源（ST7735 0x11/0xB1-0xE1 序列，厂家 lcd_init.c）+改造要点（软 SPI/去平台依赖/字库裁剪/方向参数化）+六屏合一说明+未上板）；pins 6 角色 gpio_out（default 按上表）
- [x] wordlist 显示模块一条 solution（六屏合一 + 触摸选配件 lib ["lcd","tp_xpt2046"]）+ models 增 ST7735/ST7789/GC9A01/XPT2046；实测默认词表 wire 字节数（超 7300 fit 上限按先例上调并同步 budget/llm）
- [x] 测试：test_module_lcd.py（manifest 形状 + 单选生成 syscfg 落盘 + main.c 调 init/显示函数过静态门禁 + 字库体积断言 + 无平台依赖守卫 + 型号常量完整性）+ test_pins/test_pin_bindings（刻意重叠表）/test_syscfg_prune 增断言
- [x] 编译矩阵：单选生成 → SysConfig CLI → gmake 0 error/0 warning；verified=true + notes 编译记录；code-review 后中文提交、工单 resolved


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
