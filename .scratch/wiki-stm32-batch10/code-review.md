# 批 10 code-review 两轴报告

- **固定点**：工作树未提交变更（vs HEAD）。变更面 = `library/modules/{vl53l0x,max7219,lcd,tp_xpt2046,oled,ili9341,ili9488}/`、`library/masters/stm32/pin_config.h`、`tests/`（test_module_vl53l0x/max7219/lcd/tp_xpt2046/oled_extra/ili9341/ili9488.py + test_pins.py + test_default_layout.py + test_llm.py 相关）、`src/contest_generator/wordlist.json`、`.scratch/wiki-stm32-batch10/` 与 `.scratch/wiki-stm32-batch4/matrix/` 脚本、`CONTEXT.md`。工作树另含少量**与本批无关**的既有改动（`.scratch/wiki-md-repair/*`、`.scratch/wiki-stm32-batch5/issues/06`、`.scratch/wiki-stm32-batch6/issues/07`、`tests/test_module_jq8900.py` 一行 docstring），未纳入两轴评审。
- 评审范围共 **8 件**：批次 10 的 01-07（6 个模块目录 + oled 两工单同文件）+ 批次 4/05 vl53l0x。

---

## 规格轴（逐条）

### 01 — max7219（数码管/点阵 3 脚打样）— ✓ 兑现
- API 6 函数与 mspm0 同名同型完全对齐（`max7219_init(form,brightness)`/`write_digit`/`write_matrix`/`write_reg`/`clear`/`set_chip_count`；FORM_DIGIT 0 / MATRIX 1）。
- 软 SPI 3 脚位操作（gpio_set + OUT_PP），零引脚字面量；页原式寄存器族 0x09/0x0A/0x0B/0x0C/0x0F 保留；演示字模表（disp1[12][8]）不入库；两页合并单模块双形态。
- 默认脚 DIN=PC13/CLK=PC14/CS=PC15（叠板载 LED 三灯，输出指示互替）——manifest/pins/test_pins 钉值/test_default_layout 白名单（PC13-15 组）四处一致。
- manifest stm32 条目：files 2 件、deps `()`（无 delay 调用——照 mspm0 现状）、pins 3 行、verified=true、notes 含两页合一/演示字模不入库/未上板/编译矩阵 Code=1868。
- UV4 矩阵 0 error/0 warning（run_max7219_matrix.py）；wordlist 零补录复核（已挂接）。

### 02 — lcd 六屏合一彩屏 — ✓ 兑现
- API 全族 14 函数与 mspm0 lcd.h 对齐（init(model,dir)/get_width/height/fill/clear/draw_point/line/rectangle/circle/show_char/string/num/float/chinese16x16/picture；LCD_MODEL_096..180 六模型 + LCD_DIR_DEFAULT 0xFF）。
- 分层 = lcd_stm32.c 单文件自实现（绘制层/序列表/模型表自 mspm0 逐行移植、仅总线层换 gpio_set），lcdfont.h **双平台共用同一份文件**（files 含 code/lcdfont.h）。
- 软 SPI 6 脚默认 PB4/PB5/PA5/PB6/PB7/PA15；与 oled SPI 五脚组（子集）/max7219 三脚组显示族互替同脚；与 tp 配套件刻意错开——notes/白名单/test_pins 一致。
- F4 混写甄别（0-96/1-47 两页软 SPI 块 F4 → F1 ml_gpio）记录；0-96 页无 SCLK/MOSI 宏记录；pic.h/zk.c/演示位图不入库。
- manifest：files 3 件、deps `("delay",)`（mspm0 侧 lcd_init.c include delay.h 支撑）、pins 6 行、verified=true、notes 含字库 ≤16KB/性能 0.27s/未上板/矩阵 Code=3760。

### 03 — tp_xpt2046 触摸屏 — ✓ 兑现
- API 5 函数与 mspm0 对齐（init/set_calibration/read_raw/read_xy/is_pressed）；命令 0xD0/0x90、5 次中值滤波（升序去头尾 1 取均值）、PEN 轮询无中断（无 EXTI/NVIC/IRQHandler）。
- 默认脚 CS=PB12/CLK=PB13/DIN=PB14/DOUT=PB15/PEN=PB0（触摸按键×屏幕触摸互替同脚；与 lcd 刻意错开）——manifest/钉值/白名单一致。
- 出厂预设方向 1 校准值（0.034810/0.043057/-5/-7）与 mspm0 同款；TP_Adjust 流程不入库（ADR 0009）。
- 软 SPI 5 脚位操作 + delay_us(1/6) 节拍；未上板 note；矩阵 0/0（Code=3100）。

### 04 — oled SPI/0.91 变体补缺口（C 类）— ✓ 兑现
- stm32 files `[]` → `[code/oled_extra_stm32.c, code/oled_extra_stm32.h]`；I2C 路径零改动（既有 OLED_GPIO/OLED_SCL_Pin/OLED_SDA_Pin=PB8/PB9 保留 + 测试断言 ml_oled.h 无 SPI 符号混入）。
- `oled_spi_init()` 软 SPI 5 脚（PB4/5/6/7/PA5 = lcd 组子集互替同脚）+ SSD1306 序列；`oled_set_res(OLED_RES_128X32)`（MUX 0x1F/COM 0x00 分支，init 前调用）；小写族 `oled_spi_show_text/show_number` 等全带 `oled_spi_` 前缀（母版 ml_oled 占用 OLED_Show*/oled_show_* 不可改名——notes 记录）。
- 字库 = `extern const unsigned char OLED_F8x16[][16];` 复用母版 ml_oled_font.h 的全局定义（不 include 本体避免重复定义链接错）——类型与母版定义逐字匹配，无重定义冲突。
- F4 混写甄别（0-96-single-spi L96-103）记录；0.91 = 分辨率变体非新序列记录；矩阵 I2C+SPI 双路径 0/0（Code=2974）。

### 05 — oled SH1106 变体 — ✓ 兑现
- `oled_init_sh1106()` 专属序列（0xAE 关/列偏移 0x02 0x10/0x40/0xB0/0x81 0xCF/0xA1/0xA6/0xA8 0x3F/0xAD 0x8B 0x33/0xC8/0xD3 0x00/0xD5 0x80/0xD9 0x1F/0xDA 0x12/0xDB 0x40/清屏/0xAF 开——页面 L116-142 A 类直提）+ 刷新列偏移 0x02 分支（`low_col = s_sh1106 ? 0x02 : 0x00`）。
- 与 04 同文件同矩阵；mspm0 未提炼过 SH1106（首次落码）记录；测试守卫 0xAD/0x8B/0x33/0x02 全绿。

### 06 — ili9341（B 类新 slug）— ✓ 兑现
- 仅 stm32 平台条目；B 类口径 deps `()`（delay 走母版内嵌 ml_delay——库内 B 类先例 ec11/key_matrix 同款）。
- 资料取自 lcdwiki MSP2807 包（**软 SPI 版**例程为准——页面链接原标硬件 SPI 版，记录）；引脚表/序列/16bit（0x3A 0x55）/MADCTL 方向表（0x08/0x68/0xC8/0xA8）全部取自包内；FONT.H 不入库（GBK 大字号）。
- API 照 mspm0 lcd.h 风格 15 函数（ili9341_ 前缀），无 lcdwiki 旧壳（POINT_COLOR/BACK_COLOR/LCD_ShowString/lcddev 未出现——守卫验证）。
- 字库 = `ili9341_font.h`（lcdfont.h 同源副本）：头守卫改名 `__ILI9341_FONT_H`、三数组 `static const`（ascii_1206/ascii_1608/tfont16）、`typedef struct` 不 static（typedef 本就无链接性）——static 化 + 各模块 .c 单独 include（不同 TU），双选安全。
- 默认脚 = lcd 六脚组同款（PB4/5/PA5/PB6/7/PA15）——manifest/钉值/白名单/notes 一致；触摸复用 tp_xpt2046（notes，零耦合）；未上板 note；矩阵 0/0（Code=4624）；wordlist 补录（2.8/3.2/3.5 寸 ILI 大屏方案 + models ILI9341/ILI9488）。

### 07 — ili9488（B 类新 slug）— ✓ 兑现
- 与 06 同构：仅 stm32、deps `()`、API 15 函数 ili9488_ 前缀、字库副本 `ili9488_font.h`（守卫改名 + 三数组 static const + typedef 不 static）、默认脚 lcd 组同款、无旧壳/位带宏（SYSTEM/sys 位带换算 ml_gpio 不引 sys.h——守卫验证）。
- **18bit 面板 16bit 打包** = 0x3A 0x66 + 每像素 3 字节流（RED 0xF8/GREEN 0xFC/BLUE <<3）——包内原式；序列关键字节/0x11+120ms/0x29 守卫通过。
- 性能 note 全屏 ≈0.55s；未上板；矩阵 0/0（Code=4500）；wordlist 补录同 06。

### 批 4/05 — vl53l0x（B 类 ToF 测距）— ✓ 兑现（实施）/ ⚠ 工单文档未闭环
- 仅 stm32 条目：files 4 件（vl53l0x_stm32.c/h + vl53l0x_core.c/h——ST 官方 API 最小切片：闭包 75 函数 + refArrayQuadrants/REF_ARRAY_SPAD_* 数据段机械提取合并，函数体原样零改动，BSD-3-Clause 保留）。
- 引脚 3 行 = SCL=PA6/SDA=PA7（与库内软 I2C 件共总线；`⚠ 0x52(8bit)=0x29(7bit) 与 tcs34725 同址互替不可同挂` notes）、XSHUT=PB0（叠 hx711 DT/EC11 SW/rc522 CS——页面 PB7 弃用记录）；钉值/白名单（PA6/PA7/PB0）一致。
- API = `vl53l0x_init()`（XSHUT 复位 50ms×2 + DataInit）/`vl53l0x_set_mode(0-3)`（StaticInit + PerformRefCalibration/SpadManagement + 模式参数表）/`vl53l0x_read_mm(float*)`（单次测量，0=成功）；模式宏四档。
- 软 I2C = 模块内静态 `vl53l0x_iic_*` 原语族（OUT_OD/IU 共总线换算 + SCL 显式置高回修口径）；零 ml_i2c/零位带（PBout/PAin 全无——守卫验证）；地址保持上电默认 0x52（BSP 改 0x54 且未判返回值的缺陷③不照抄）；缺陷①Status 粘滞、②vl53l0x_data 无声明、⑤char ack 死变量、⑥write_word 奇地址 index+1、⑦校准缓存路径剔除等全部落地并有测试防回潮。
- UV4 矩阵 0 error/0 warning（run_vl53l0x_matrix.py——batch4 matrix 目录）；verified=true；wordlist 补录（激光测距 VL53L0X 方案 + models VL53L0X）。
- **⚠ 偏差（工单文档）**：`.scratch/wiki-stm32-batch4/issues/05-module-vl53l0x.md` 状态仍是 `claimed（资料已到位——可实施）`，实施清单 checkbox 全部未打勾、**无「结论回填」段**——与批次 10 其余工单（01-07 均 resolved + 结论回填）的口径不一致；本件实际已实施、测试全绿、verified=true，属「实施完成但工单未关闭」的流程缺口。另工单清单写 `dependencies ["delay"]`，实际 deps `()`——与库内 B 类（ec11/key_matrix）`deps []` 口径一致（delay 走母版内嵌 ml_delay），不算偏差，仅记录。

### 跨件核对的规格点
- **API 家族**：max7219 6 / lcd 14 / tp 5 / oled extra（oled_spi_init + oled_set_res + oled_init_sh1106 + show 族）/ ili 各 15 / vl53l0x 3+模式宏——全部与 mspm0 .h 或 spec⑥ 对齐 ✓。
- **字库复用**：lcd = lcdfont.h 双平台同一份文件；ili 两件 = lcdfont.h 同源副本（改名 + static 化）；oled = 母版 ml_oled_font.h extern 复用；vl53l0x 无字库需求 ✓。
- **互替同脚**：lcd 六脚组 ⊃ oled SPI 五脚组（均 PB4/5/6/7/PA5）、max7219 PC13-15、ili 两件 = lcd 组同款；tp PB12-15/PB0 与 lcd 刻意错开；vl53l0x PA6/PA7/PB0 —— 与 spec⑤ 逐一配对 ✓。
- **测试守卫**：各模块 BANNED_CODE_PATTERNS（printf/GPIO_Init/RCC_/stm32f10x.h/PBout/PAin/ml_oled 重定义/DL_/ti_msp_dl_config/POINT_COLOR/LCD_ShowString）+ 序列字节 + 字库预算 + I2C 零变化断言——全部在位且通过 ✓。
- **verified 回写**：8 件 manifest verified=true ✓；**wordlist 补录**：ili9341/ili9488/vl53l0x 补录（models + 方案 + lib_modules），max7219/lcd/oled/tp 零补录复核 ✓；默认词表完整送达预算测试绿（未截断）✓。

---

## 标准轴（问题清单）

未见 [高]/[中] 级问题；以下为 [低] 级观察项（均不影响编译/门禁）：

1. **[低] `tests/test_default_layout.py`（L375-378）**：PC14 黄灯组的同一段两行注释被重复贴了两遍（`# PC14 黄灯组（wiki-stm32-batch9/02…同选经绑定消解）` ×2）。建议删除重复的一份，只保留「**wiki-stm32-batch10/01**：max7219 CLK 并入 PC14」新增注释。
2. **[低] `tests/test_module_vl53l0x.py` / `test_module_ili9341.py` / `test_module_ili9488.py` 的 docstring**：均写「依赖 delay」而断言 `manifest.dependencies == ()`（B 类 deps [] 口径——delay 走母版内嵌 ml_delay，非模块依赖）。建议 docstring 改为「delay 走母版内嵌（deps [] B 类口径）」以免误导后续维护者。
3. **[低] `.scratch/wiki-stm32-batch10/sweep_8_modules.py`**：文件名 `8` 与实际 CHECK 键数 **7**（vl53l0x/max7219/lcd/tp_xpt2046/oled/ili9341/ili9488）不符（推测把 oled 04/05 两工单或「8 件」口径算入）。建议改名 `sweep_7_modules.py` 或在文件头注明「8 = 7 模块 × oled 双工单」。
4. **[低] `.scratch/wiki-stm32-batch4/issues/05-module-vl53l0x.md`**：实施/测试/矩阵/verified 全部完成，但工单状态仍 `claimed`、无结论回填（规格轴已述，流程文档闭环缺一步）。
5. **[低] `library/modules/lcd/code/lcdfont.h`**：本次仅补了文件末尾换行（`\ No newline at end of file` → 空行），内容零变化——良性修复，不影响双平台共享。
6. **[低] 显示族头文件颜色宏重复定义（推断项）**：`lcd_stm32.h`/`ili9341_stm32.h`/`ili9488_stm32.h` 各自 `#define WHITE/BLACK/RED…`（值相同）。若用户同时选中两个显示模块并在同一 main.c TU 中 include 两个头，宏替换列表相同 → C 标准允许的合法重定义，不报错；且显示族为互替件「一次选一块屏」。无需修改，记录观察。
7. **[低] `oled_extra_stm32.c`（观察项）**：`oled_spi_show_char` 的 `page = y/8`、`page+1` 无上限钳制（y 超出 56 时 page+1 可达 8，GRAM[144][8] 越界写）。与 mspm0 oled.c「显存页数由调用方按分辨率控制」同一契约（128×64 用 0-7 页、128×32 用 0-3 页），库内先例同款；建议后续在 notes 补一行「调用方 y 须 0..56」或函数内 clamp（可选，不阻塞）。

**规范面肯定项**（与库内先例 bmp180_stm32.c / neo_6m / lcd mspm0 / max7219 mspm0 对照）：
- 函数命名 `模块_语义` 小写 snake、注释口径（来源页/改造要点/电平口径/缺陷修正/未上板）一致；
- 零引脚字面量（`GPIO_A/Pin_N/TIM/ADC_Channel` 在注释剥离后全部无命中）；
- 无 printf / 单个 GPIO_Init 组调用 / RCC_ 残留（stm32 文件逐文件扫描零命中；mspm0 平台文件中的 DL_/ti_msp_dl_config 属预期，不进 stm32 工程）；
- 无 sys.h 位带（PBout/PAin）；无母版 ml_i2c 调用（vl53l0x 自实现 `_iic_*`）；
- 字体副本处理：`static const` 三数组 + typedef 不 static + 头守卫改名为 `__ILI9341_FONT_H`/`__ILI9488_FONT_H`（与原件 `__LCDFONT_H` 不冲突）+ 头基名唯一（`ili9341_font.h`/`ili9488_font.h` 与 `lcdfont.h` 各属其模块，test_module_independence 门禁通过）；
- deps：A 类双平台件（lcd/tp/oled）保持 `("delay",)`（mspm0 文件实际 include），B 类仅 stm32 件（vl53l0x/ili9341/ili9488）`deps []`——与库内 B 类口径一致，无死依赖/隐藏耦合。

---

## 抽检记录

| 检查 | 命令 | 结果 |
|---|---|---|
| 引脚字面量 + 声明/宏不变量 | `pytest tests/test_pins.py -q`（含 `test_module_code_has_no_pin_literals`、`STM32_MACRO_VALUES` 钉值） | ✅ 通过（并入下方 66 全绿） |
| 模块独立性门禁（隐藏耦合/死依赖/头基名唯一/环） | `pytest tests/test_module_independence.py -q` | ✅ 通过（并入 66） |
| 七模块 + 默认布局测试 | `pytest tests/test_module_vl53l0x.py test_module_max7219.py test_module_lcd.py test_module_tp_xpt2046.py test_module_oled_extra.py test_module_ili9341.py test_module_ili9488.py test_default_layout.py -q` | ✅ 66 passed in 5.79s（含上述 pins/independence 合计） |
| wordlist 默认词表完整送达 + 预算 | `pytest tests/test_llm.py::test_wordlist_segment_covers_default_wordlist_and_budget -q` | ✅ 1 passed |
| 注释剥离后残留扫描（8 件 stm32 文件） | 自写 clex `strip_comments` 扫描 `printf\|GPIO_Init\|RCC_\|DL_\|ti_msp_dl_config\|PBout\|PAin\|ml_i2c\|POINT_COLOR\|LCD_ShowString` | ✅ stm32 文件零命中；命中仅限 mspm0 平台文件（max7219.c/lcd_init.h/tp_xpt2046.c/oled.c/oled.h——预期不进 stm32 工程） |
| UV4 真编译矩阵 | `matrix/{max7219,lcd,tp_xpt2046,oled_extra,ili9341,ili9488}/build.log` + `.scratch/wiki-stm32-batch4/matrix/vl53l0x/build.log` | ✅ 7/7 均 `0 Error(s), 0 Warning(s)` |
| 一键一致性快检 | `python .scratch/wiki-stm32-batch10/sweep_8_modules.py` | ✅ SWEEP OK（7 件） |
| 字体 static/守卫/头基名 | 人工读 `ili9341_font.h`/`ili9488_font.h` + `test_module_independence.py::_header_owners` + 模块测试 `字库 ≤17KB` 断言 | ✅ 三数组 `static const`、typedef 不 static、守卫改名、基名唯一 |
| 默认脚配对 | manifest pins + pin_config.h + test_pins STM32_MACRO_VALUES + test_default_layout 白名单 | ✅ lcd/oled/ili 六脚组（PB4/5/PA5/PB6/7/PA15）、max7219 PC13-15、tp PB12-15/PB0、vl53l0x PA6/PA7/PB0 四处一致 |

**总评**：规格轴 8 件全部兑现（唯一 ⚠ = 批 4/05 工单文档未闭环：状态仍 claimed、无结论回填）；标准轴未见高/中级问题，仅 7 条 [低] 级观察项（注释重复、docstring 表述、脚本命名、工单闭环、文件末尾换行、颜色宏同名重定义推断、oled 页边界契约）。
