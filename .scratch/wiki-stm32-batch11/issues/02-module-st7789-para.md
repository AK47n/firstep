# 02 — st7789_para 1.14 寸 8 位并口彩屏（B 类新 slug · 仅 stm32 · 资料已到位，手册 screen--1-14-color-screen.md）

**要做什么：** 模块库新增 **`st7789_para`**（库内无此模块——B 类，**仅 stm32 平台条目**——库内首个**8 位并口（8080 接口）显示件**，与 lcd 全系软 SPI 驱动结构不同）：从**立创移植工程包**提炼 ST7789V 135×240 并口驱动为纯驱动切片（8 位数据线 + RD/WR/CS/DC/RES/BLK 控制线，总线走 GPIO 位操作（gpio_set——8080 时序 RD/WR 选通脉冲忙等，不占 TIMER/FSMC），API 照 mspm0 lcd.h 风格：`st7789_para_init(dir)`（LI_ST7789 序列——**包内 lcd_init.c 直提**）+ `st7789_para_get_width/height` + `st7789_para_fill/clear/draw_point/line/rectangle/circle` + `st7789_para_show_char/string/num/float/picture`（绘制层照 mspm0 lcd.h 风格；**不引 lcdwiki 旧壳**；包内 pic.h 演示位图不入库——mspm0 先例）。

**✅ 资料已到位（2026-09，用户下载并解压）**：`sources/materials/lckfb-地阔星移植手册/网盘下载/st7789_para/`——**立创 8 位并口移植成功工程**（436KB 纯代码）：
- `bsp/LCD/lcd.c + lcd.h`（绘制层 + **字体/颜色宏**——lcd.h 含 RGB565 色值宏/`USE_HORIZONTAL 2` 方向宏）
- `bsp/LCD/lcd_init.c + lcd_init.h`（**ST7789V 初始化序列 + 引脚宏表（并口 14 脚）**：默认 RD=PA5/WR=PA4/CS=PA2/DC=PA3/RES=PA1/BLK=PA0/DB0=PA6/DB1=PA7/DB2=PB0/DB3=PB1/DB4=PB10/DB5=PB11/DB6=PB12/DB7=PB13——**全撞既有占用，不照抄**）
- `bsp/LCD/lcdfont.h`（包内字库——**按 ili 两件先例做同源副本 `<slug>_font.h`（头基名唯一+static 化）**或与库内 lcdfont.h 复用（实施时按字符集比对——优先库内 lcdfont.h 同源，若字符集差异大则包内副本，notes 记录；**跨模块同名文件冲突门禁（L6200E）——不直接引用包内 lcdfont.h 名**）
- `app/main.c`（演示——剔除）、`bsp/uart/bsp_uart`（剔除）、工程模板躯壳（不随）

**被谁阻塞：** ~~用户提供资料~~ **资料已到位——可立即开始**（stm32 线收官最后一件；上后 A/B/C 全部完成）。

**引脚与默认脚（14 脚——stm32 32 脚全占局面的重拍，同选概率最低 + 白名单登记 + 实施可微调记 notes；现实约束：并口屏吃 14 脚、重叠面大，同选冲突经绑定消解为高概率动作，与显示族（lcd/oled/max7219/ili 系）互替——一次只选一块屏）：**
- pins 14 行：`ST7789_PARA_DB0..DB7`（gpio_out，default **PB4/PB5/PB6/PB7/PB0/PB1/PB3/PA8**）+ `ST7789_PARA_RD`（gpio_out，**PA5**）+ `ST7789_PARA_WR`（gpio_out，**PA4**）+ `ST7789_PARA_CS`（**PC13**）+ `ST7789_PARA_DC`（**PC14**）+ `ST7789_PARA_RES`（**PC15**）+ `ST7789_PARA_BLK`（**PA15**）——macros 28 个（逐脚端口宏 `ST7789_PARA_DB0_GPIO/_DB0_PIN` 族——照批 2 逐脚宏先例）。
- pin_config.h 宏段 28 宏（注释：数据线叠「传感/运动/输入」类（relay+ENC/hx711+EC11/servo+GRAY/human_ir/hx711+DS18B20+EC11/KEY+GRAY+dht11/IR_BEAM+WS2812+GRAY——屏（输出）与这些采集/运动/输入件不同框相对最低）；控制线 CS/DC/RES/BLK 叠板载 LED 三灯+蜂鸣（**显示替代指示互替**——max7219 PC13-15 先例）；RD/WR 用 PA4/PA5（叠微波+EC11/flame+ADC 组——不同框）；与显示族互替；同选经绑定消解）。

**状态：** resolved（2026-09 实施完成——B 类收官件，stm32 线 A/B/C 全收官）。

**实施清单：**
- [x] `library/modules/st7789_para/` 新目录：code/st7789_para_stm32.c/.h（API 照 mspm0 lcd.h 风格命名（ili 两件同款——`st7789_para_` 前缀）；.c 8080 并口位操作（DB0-7 并行写 + RD/WR 选通忙等——页面包原式换算 gpio_set）+ 初始化序列（lcd_init.c 直提——**ST7789V 135×240，USE_HORIZONTAL 方向宏化**）；绘制/文本 API 照 mspm0 lcd.c 结构移植（绘图层零 mspm0 依赖；**pic.h 演示位图不入库**）；零引脚字面量）
- [x] `manifest.json`（**仅 platforms.stm32**：files `[code/st7789_para_stm32.c, code/st7789_para_stm32.h, code/st7789_para_font.h]`、dependencies []、verified 初 false、hardware_bound false、pins 14 行、kit（1.14 寸 TFT 并口屏——页面采购链接）、source_url（wiki 原页 `.../screen/1-14-color-screen.html` + **立创移植工程来源（网盘——notes）**）、notes（**B 类口径+8 位并口（库内首个并口显示件——与 lcd 软 SPI 族驱动结构不同）**+资料来源+引脚重拍记录（包默认 14 脚全弃用）+字库副本决策+pic.h 不入库+14 脚现实约束+未上板）+ description（能力方向：1.14 寸彩屏显示/并口驱动；无题绑定）
- [x] pin_config.h 增 28 宏
- [x] 测试 `tests/test_module_st7789_para.py`（B 类模板：仅 platforms.stm32 + pins 14 行/macros 28 + 单选生成全流程 + 守卫：无 `POINT_COLOR`/`LCD_ShowString` 旧壳、无 `FSMC`（不用 FSMC——GPIO 位操作）、无 pic.h 位图数组、`135`/`240` 分辨率、API 断言（init/fill/show_string 族）、无 printf/GPIO_Init/RCC_）
- [x] test_pins.py 补 28 宏；test_default_layout.py 白名单 14 脚登记（显示组——PB4/5/6/7/PB0/1/PB3/PA8/PA5/PA4/PC13-15/PA15——含 max7219 组/传感器组并列登记）
- [x] UV4 矩阵（init+get_width/height+fill+clear+draw_point+line+rectangle+circle+show_char+show_string+show_num+show_float+chinese16x16+show_picture 全调，(void) 化）→ 0/0 → verified=true
- [x] wordlist 补录（显示模块/并口屏 + models + lib_modules）
- [x] 中文提交 → resolved → 结论回填（资料源/引脚重拍/8080 时序/字库决策）

**结论（2026-09 实施完成）**：B 类新 slug 落地——library/modules/st7789_para/（code/st7789_para_stm32.c/.h + code/st7789_para_font.h（**库内 lcdfont.h 同源副本**——字符集比对：包内 lcdfont.h 与库内同源（ascii_1608 逐字节一致、tfont16 五字同形同阵仅 GBK 索引写法不同——包内用 C 字符串字面量、库内 {0xD6,0xD0} 标准形式）；**API 口径（sizey 12/16 + chinese16x16）需要 ascii_1206——包内无此套** → 采用库内同源副本；头基名唯一门禁改名 + 数组 static 化防双选链接重复））；**8080 并口位操作**（包内 LCD_Writ_Bus 原式：每字节 CS 低→WR 低→8 位数据线并行置数（DB7..DB0）→ WR 高（写选通上升沿）→ CS 高；RD 只用于读方向——包内/本件仅写显示、RD 保持高不参与；gpio_set 换算，不引 sys.h 位带宏；**不用 FSMC/硬件外设/TIMER**）；初始化序列 = 包内 LCD_Init 原式直提（0x11+120ms/0x36(方向表)/0x3A 0x05(16bit 65K)/0xB2/0xB7/0xBB/0xC0/0xC2/0xC3/0xC4/0xC6/0xD0/0xE0/0xE1/0x21/0x29——**USE_HORIZONTAL 宏方向化 = 运行时 dir 表**：MADCTL 0x00/0xC0/0x70/0xA0 + 地址偏移表 52/53/40/40 × 40/40/53/52；dir 0/1 竖屏 135×240、2/3 横屏 240×135；默认 = 包 USE_HORIZONTAL=2 横屏）；API 照 mspm0 lcd.h 风格（不照 lcdwiki 旧壳：lcddev/POINT_COLOR/LCD_ShowString 弃用；含 show_chinese16x16——与 ili 两件同款）；**默认 14 脚 = 工单重拍**（包默认 14 脚全弃用——全撞既有占用；DB0-7=PB4/5/6/7/PB0/1/PB3/PA8、RD=PA5/WR=PA4、CS=PC13/DC=PC14/RES=PC15/BLK=PA15——数据线叠采集/运动/输入类不同框、控制线叠板载灯+蜂鸣输出指示互替、与显示族互替——一次一块屏）；pic.h 演示位图不入库（show_picture 收外部点阵）；pin_config.h 28 宏 + 测试全绿（序列字节/MADCTL 表/偏移表/无旧壳/无 FSMC/无位带宏/字库 ≤17KB 副本预算）；UV4 矩阵 **0 error / 0 warning** → verified=true（run_st7789_para_matrix.py——Program Size: Code=4844/RO-data=3112）；wordlist 显示模块组补录（1.14 寸 ST7789 并口屏方案 + models ST7789 并口屏）；**未上板**（8080 时序/偏移/反色/背光真机验证留后续——真机清单记录）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。**完成后 = stm32 线 A/B/C 全收官**（77 页全对应：A 61+B 9+C 7）。
