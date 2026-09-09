# 05 — oled SH1106 变体（1.3 寸单色 OLED，手册 screen--1-3-single-oled-screen.md）

**要做什么：** 模块库 `oled` 的 **stm32 侧补 SH1106 变体**（C 类，与工单 04 同批同模式）：`oled_extra_stm32.c/.h`（工单 04 的同一文件）增 **SH1106 初始化变体**——`oled_init_sh1106()`（**专属序列：0xAD（DC 使能）/0x8B（行映射）+ 0x33（PLL）+ 列偏移 0x02——页面 L116-142 页内完整**；SPI 总线走工单 04 的软 SPI 原语；SH1106 ≠ SSD1306 初始化序列——独立变体函数），字库复用 oledfont.h（128×64 同分辨率）。

**关键事实（%TEMP%\batch10-facts.md）：** F1；页面标题 1.3 单色 OLED（ZJY130S0700WG01——SH1106 128×64）；**mspm0 未提炼过 SH1106**（仅核对该家族「同家族仅核对不提炼」——本工单首次落码：页内序列完整 + 字库库内 → A 类直提口径）；页面默认脚不照抄。

**引脚：** 同工单 04（OLED_SPI_SCL/SDA/DC/CS/RES = PB4/PB5/PB6/PB7/PA5）——SH1106 走同一软 SPI 组（互替同脚——一次选一块屏）。

**被谁阻塞：** 无——可立即开始（建议与工单 04 同一实施者连着做——共用 oled_extra_stm32.c）。

**状态：** resolved（2026-09 实施完成）。

**实施清单：**
- [x] `library/modules/oled/code/oled_extra_stm32.c/.h` 增 `oled_init_sh1106()`（SH1106 序列 + 列偏移 0x02——页面原式；与 SSD1306 变体同 API 风格）
- [x] manifest.json platforms.stm32 notes 追加（SH1106 变体：页内序列完整/列偏移/与 SSD1306 差异说明——mspm0 未提炼（首次））
- [x] 测试 `tests/test_module_oled_extra.py` 增：`oled_init_sh1106` 存在 + SH1106 序列守卫（`0xAD`/`0x8B`/`0x33`/列偏移 `0x02`）+ 128×64 分辨率注释
- [x] UV4 矩阵增 SH1106 初始化调用（同工单 04 矩阵——两条变体路径都调，(void) 化）→ 0/0（与工单 04 同矩阵/复核）
- [x] 中文提交 → resolved → 结论回填（与工单 04 同一提交或紧随——记录）

**结论（2026-09 实施完成，与工单 04 同文件同一矩阵）**：oled_extra_stm32.c 增 oled_init_sh1106()——专属序列（0xAE 关/列偏移 0x02 0x10/0x40/0xB0/0x81 0xCF/0xA1/0xA6/0xA8 0x3F/0xAD 0x8B 0x33/0xC8/0xD3 0x00/0xD5 0x80/0xD9 0x1F/0xDA 0x12/0xDB 0x40/清屏/0xAF 开——页面 L116-142 A 类直提）+ s_sh1106 刷新列偏移 0x02 分支；**mspm0 未提炼过 SH1106——本件首次落码**（notes 记录）；manifest notes 追加（SH1106 变体说明）；测试守卫（0xAD/0x8B/0x33/列偏移 0x02）全绿；UV4 矩阵与工单 04 同一矩阵 0 error/0 warning。

**验收标准：** 与工单 04 合并验收：pytest 绿；矩阵 exit 0；I2C 路径零回归。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
