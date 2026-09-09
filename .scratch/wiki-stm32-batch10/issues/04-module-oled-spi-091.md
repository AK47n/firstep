# 04 — oled SPI/0.91 总线变体补缺口（C 类，手册 screen--0-96-single-spi-screen.md + screen--0-91-color-screen.md）

**要做什么：** 模块库 `oled` 的 **stm32 侧补缺口**（mspm0 零改动）：当前 stm32 条目 files=[]（母版内嵌 ml_oled——**仅 I2C 128×64**），本工单新增 **SPI 总线变体 + 0.91 寸（128×32）分辨率变体**：`code/oled_extra_stm32.c/.h`——`oled_spi_init()`（软 SPI 5 脚：SCL/SDA（DC/CS/RES）——照 mspm0 `OLED_SPI_Init` 决策 B「同芯片同 API 仅总线层」结构）+ `oled_set_res(OLED_RES_128X32)`（0.91——须 init 前调用；mspm0 核验值：MUX 0x1F/COM 0x00——页面 L174 半周期 2us + 序列页内完整）+ `oled_show_text/oled_show_number/oled_refresh` 等双平台小写 API 族沿用（与既有 API 一致）；字库复用母版 ml_oled 的 oledfont.h（37.8KB——不变）。

**关键事实（%TEMP%\batch10-facts.md）：** 0-96-single-spi 页**软 SPI 块 F4 混写**（L96-103——改写 F1）；0-91 页「彩屏」标题实为 SSD1306 128×32 单色（MUX 0x1F/COM 0x00 序列与 mspm0 oled_set_res 核验值一致）；两页页面默认脚（mspm0 板脚）不照抄；**I2C 路径（母版 ml_oled + manifest pins OLED_SCL/SDA=PB8/9）零改动**。

**引脚（新增 SPI 角色，与 lcd 组互替同脚）：** pins 增 `OLED_SPI_SCL`（gpio_out，default **PB4**）/ `OLED_SPI_SDA`（**PB5**）/ `OLED_SPI_DC`（**PB6**）/ `OLED_SPI_CS`（**PB7**）/ `OLED_SPI_RES`（**PA5**）——macros 10 个（逐脚端口宏；注释：与 lcd 六脚组**互替同脚**（大屏/小屏一次选一——互替同脚先例）；既有 OLED_SCL/SDA（PB8/9，I2C 内嵌）保留不动）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved（2026-09 实施完成）。

**实施清单：**
- [x] `library/modules/oled/code/oled_extra_stm32.c/.h`（.c：软 SPI 5 脚位操作 + SSD1306 SPI 初始化序列（页面/ mspm0 同参）+ `oled_set_res` 变体（128X32——复用既有 oled_set_res 签名改造? **照 mspm0 实现：oled_set_res 已存在（母版? mspm0 files 含 oled.c——stm32 侧 oled_set_res 在 extra 中实现**——实施时对照 mspm0 oled.c 的 oled_set_res（放模块 oled.c 还是母版——以 mspm0 为准）；零引脚字面量）
- [x] manifest.json platforms.stm32：files 从 [] → `["code/oled_extra_stm32.c", "code/oled_extra_stm32.h"]`、pins 增 5 行（SPI 角色——既有 I2C 2 行保留）、notes 追加（C 类补缺口：SPI/0.91 变体——mspm0 批 12/07 决策 B 同构；F4 混写甄别记录；I2C 路径零改动）
- [x] pin_config.h 增 10 宏（OLED_SPI_* 段）
- [x] 测试 `tests/test_module_oled_extra.py`：**I2C 路径零变化断言**（母版 ml_oled 头/既有 pins 不动）+ SPI 变体（5 脚宏存在 + `oled_spi_init` 存在 + `OLED_RES_128X32` + MUX `0x1F`/COM `0x00`）+ 单选生成（含既有 oled 用例回归）+ 守卫（无 printf/GPIO_Init/RCC_、软 SPI 无硬件 SPI 调用）
- [x] test_pins.py 补 10 宏；test_default_layout.py 白名单 PB4/5/6/7 +4、PA5 +1（显示组——与 lcd 同组登记）
- [x] UV4 矩阵（oled 单选：I2C 路径 + SPI 路径各一组——oled_set_res(OLED_RES_128X32)+oled_spi_init()+oled_show_text(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论（2026-09 实施完成）**：stm32 侧补缺口落地——code/oled_extra_stm32.c/.h（oled_spi_init（软 SPI 5 脚 + SSD1306 序列——MUX 0x1F/COM 0x00 128×32 分支）+ oled_set_res(OLED_RES_128X32)（与 mspm0 签名同义——I2C 路径零影响）+ SPI 显示族 oled_spi_show_text/show_number/refresh 等（**命名 oled_spi_ 前缀**：母版 ml_oled 占用 OLED_Show*/oled_show_* 且不可改名/重定义——I2C 路径零改动，notes 记录）；字库 extern 复用母版 ml_oled_font.h OLED_F8x16（防 include 重复定义链接错））；manifest platforms.stm32 files [] → 两件 + pins 增 SPI 五角色（PB4/5/6/7/PA5——lcd 组子集互替同脚）+ notes 追加（C 类补缺口/F4 混写甄别/0.91 分辨率非新序列/SH1106 归工单 05）；pin_config.h 10 宏 + 测试（含 I2C 路径零变化断言）全绿；UV4 矩阵 0 error/0 warning（run_oled_extra_matrix.py——Code=2974——I2C+SPI 双路径 main）；wordlist 零补录复核。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0；既有 I2C oled 测试全绿（零回归）。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
