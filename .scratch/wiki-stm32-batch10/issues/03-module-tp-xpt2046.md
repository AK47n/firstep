# 03 — tp_xpt2046 触摸屏（软 SPI 5 脚，手册 screen--1-8-touch-color-screen.md）

**要做什么：** 模块库 `tp_xpt2046` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼 XPT2046 电阻触摸驱动为纯驱动切片（软 SPI 5 脚：CLK/DIN/CS 输出 + DOUT/PEN 输入；与 lcd 屏零耦合——配套件刻意错开默认脚），API 与 mspm0 版**同名同型完全对齐（tp_xpt2046.h 核验）**：`xpt2046_init()`（出厂预设=1.8 寸方向 1）+ `xpt2046_set_calibration(xfac,yfac,xoff,yoff)` + `xpt2046_read_raw(12 位 0xD0/0x90，5 次中值滤波)` + `xpt2046_read_xy()` + `xpt2046_is_pressed()`（PEN 轮询——不注册中断）。

**关键事实（%TEMP%\batch10-facts.md）：** F1；页内 TP_Write_Byte(u16)/TP_Read_AD 硬 SPI 改法——stm32 软 SPI 换算（mspm0 版已软 SPI 5 脚）；驱动+校准（Adujust）结构照 mspm0；页面默认脚不照抄；**与 lcd 屏（1.8 变体）同页使用但两件零耦合**（屏侧归 lcd 模块——1.8 触摸页的屏侧 lcd.h 变体已含于 mspm0 lcd 六合一）。

**引脚与默认脚（配套 lcd 刻意错开）：**
- pins：`TP_XPT2046_CS`（gpio_out，default **PB12**）/ `TP_XPT2046_CLK`（**PB13**）/ `TP_XPT2046_DIN`（**PB14**）/ `TP_XPT2046_DOUT`（gpio_in，**PB15**）/ `TP_XPT2046_PEN`（gpio_in，**PB0**），macros 10 个（逐脚端口宏）。
- pin_config.h 10 宏（GPIO_B/Pin_12-15 + GPIO_B/Pin_0——注释：CS/CLK/DIN/DOUT 叠 DIP+GRAY+ttp224（**触摸×触摸互替同脚先例**）+键盘 ROW（输入件邻域）；PEN 叠 hx711 DT+EC11 SW（触摸×称重/旋钮不同框）；**与 lcd 六脚组刻意错开**（屏+触配套同选——mspm0 批 12 同款）；同选经绑定消解）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved（2026-09 实施完成）。

**实施清单：**
- [x] `library/modules/tp_xpt2046/code/tp_xpt2046_stm32.c/.h`（独立 stm32 头——API 5 函数照 mspm0 tp_xpt2046.h；.c 软 SPI 5 脚 + 5 次中值滤波 + PEN 轮询；零引脚字面量）
- [x] manifest.json platforms 增 stm32：files `[code/tp_xpt2046_stm32.c, code/tp_xpt2046_stm32.h]`、dependencies ["delay"]（照 mspm0）、verified false、hardware_bound false、pins 5 行、kit/source_url（wiki 原页 `.../screen/1-8-touch-color-screen.html`）、notes（手册路径+原页+网盘+**软 SPI 5 脚（页面硬 SPI 改法换算）**+校准结构+与 lcd 零耦合/配套错开+默认脚推理+未上板）
- [x] pin_config.h 增 10 宏
- [x] 测试 `tests/test_module_tp_xpt2046.py`：形状（5 pins）+宏存在+单选生成+mspm0 零改动+守卫（`0xD0`/`0x90` 命令、5 次中值滤波、PEN 轮询（无 EXTI/NVIC/IRQHandler）、无 printf/GPIO_Init/RCC_）
- [x] test_pins.py 补 10 宏；test_default_layout.py 白名单 PB12-15 组 +4、PB0 +1
- [x] UV4 矩阵（init+set_calibration(1,1,0,0)+read_raw+read_xy+is_pressed 全调，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论（2026-09 实施完成）**：stm32 条目落地——code/tp_xpt2046_stm32.c/.h（软 SPI 5 脚 gpio_set/gpio_get + 页原式 Out_PP/IPU 换算 + 五脚 init；API 5 函数与 mspm0 版同名同型完全对齐；0xD0/0x90 命令 + 5 次中值滤波 + PEN 轮询无中断）；默认脚 CS=PB12/CLK=PB13/DIN=PB14/DOUT=PB15/PEN=PB0（触摸按键×屏幕触摸互替同脚；与 lcd 六脚组刻意错开——配套同选）；pin_config.h 10 宏 + 测试全绿；UV4 矩阵 0 error/0 warning → verified=true（run_tp_xpt2046_matrix.py——Code=3100）；wordlist 零补录复核。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
