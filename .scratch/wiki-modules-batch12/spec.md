# 批次 12「彩屏/显示线」— 立创 wiki 地猛星手册模块批量入库

## 问题陈述

批次 1-11 共 46 件已入库（遥控/通信、传感器常用、显示/执行、语音/身份、I2C 增强件、环境监测/温度、气体/空气、环境类收尾、ADC 薄封装群、杂项收尾、MQ 系收尾）。`lckfb-地猛星移植手册/` 还剩 **六篇彩色屏页 + 一篇 0.96 SPI 单色页** 库内无对应条目——用户做数据显示/仪表/菜单/触摸交互题时，AI 不知道库里有驱动，只能当"需自备"。

**厂家例程已下载**（工作区外，只读引用勿拷进 git）：`C:\Users\luoji\Desktop\caiping\` 下 10 个「中景园 XXX技术资料」目录，每个含 `01-规格书与控制芯片手册.zip`、`02-*程序源码.zip`、`03-*取模教程.zip`、`04-示例图片.zip`。**源码在 zip 内**，先解压到临时目录看结构（系统 tar/Expand-Archive，本 spec 实施前已解压至 `%TEMP%\caiping-extract\` 看过：**六屏的 lcd.c/lcd.h/lcdfont.h/pic.h 字节级一致（MD5 8E3A96BE/21705389/73CDF987/87FAE079），仅 lcd_init.c/h 不同**——这是决策 A 的直接依据）。

## 方案

照批次 1-11 已确立管线，但**工作量 2-3 倍**（驱动几百行 + 字库）。厂家源码提炼（**从厂家例程 lcd.c/lcd_init.c/字库头文件取完整源码——不是 wiki 页**；wiki 页仅为移植形态与链接参考）→ 移植到库规范（软 SPI 位操作照 nrf24l01/max7219 先例、SCL/MOSI/RES/DC/CS/BLK 按引脚宏参数化 `<实例>_<引脚>_PIN/IOMUX`、BLK 背光 GPIO 输出、不占硬件 SPI 外设/TIMER——照 wiki 页"软件SPI移植"形态；厂家 51/STM32 平台代码去平台依赖：delay 走库 delay 模块、引脚宏重写、去 printf）→ 母版 syscfg GPIO 实例（LCD 六脚一实例）+ `syscfg_instances.py` INSTANCE_CONSUMERS 登记 → manifest（dependencies ["delay"]、芯片变体字段、pins、kit+source_url=wiki 原页、notes 含手册/wifi 页路径+原页+网盘链接+厂家目录路径+初始化序列来源+改造要点）→ wordlist「显示模块」补录 → 测试（tests/test_module_lcd.py：manifest 形状 + 单选生成 syscfg 实例落盘 + main.c 调 init/显示函数过静态门禁 + 字库体积断言）→ 编译矩阵 0 error/0 warning → verified → 中文提交 → resolved → code-review。

**两个结构决策先拍板（见下），再切工单。**

## 用户故事

1. 作为做题用户，我选中 `lcd`（0.96/1.28/1.3/1.47/1.69/1.8 寸任一彩屏）后，工具自动分配默认脚，生成工程打开即可编译，调用 `lcd_init(型号, 方向)` + 画点/线/圆/矩形/填充/字符/字符串/数字/浮点/汉字/图片即可显示。
2. 作为做题用户，我用 1.8 寸触摸屏时额外选 `tp_xpt2046` 读出触摸坐标；用 0.96 SPI 单色屏时选 `oled`（SPI 变体，接口不变）。
3. 作为维护者，查看每个新条目能看到平台条目（verified/kit/source_url/网盘链接/厂家目录路径/改造要点/字库策略/编译记录），可溯源到 wiki 页与厂家例程。

## 实现决策

### 既定事实（勿重新调研）

① ADC12_0 八通道已满、SysConfig 拒同外设多 UART 实例——本批无 ADC/UART 件（lcd/touch/oled-SPI 全 GPIO + 软 SPI）；② 地猛星 2×20 排针 **31 个 IO 全被默认布局占用**——本批新实例默认脚按「同选概率最低」与既有默认重叠（PA10/11=USB 勿用、PA21=VREF- 固定、PB14-17=板载 SPI flash、PA3-6=晶振未引出、PA19/20=SWD，均不可用）；③ 母版 GPIO 中断全走 GROUP1 单向量且被 motor 编码器独占——本批轮询/位操作，不注册中断；④ 软 SPI 先例 nrf24l01/max7219/rc522——GPIO 位操作忙等不占 TIMER；⑤ 工具链 `C:/ti/ccs2050`、SysConfig CLI `C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat`；⑥ 一致性快检先例 `.scratch/wiki-modules-batch10/sweep_39_modules.py` → 本批后更新；⑦ 字库/显示 API 设计对齐库内 oled（画点/字符/字符串/数字/填充——同风格出参，骨架消费一致）；⑧ **六屏厂家例程结构**（C8T6 版，`%TEMP%\caiping-extract\` 已解压核实）：`HARDWARE\LCD\{lcd.c, lcd.h, lcdfont.h, lcd_init.c, lcd_init.h, pic.h}`——lcd.c 只调 LCD_WR_*/LCD_Address_Set/字库表，**不引用 LCD_W/LCD_H 宏**（分辨率只在 lcd_init.h 宏 + lcd_init.c 偏移表中体现）；lcdfont.h = ascii_1206/1608/2412/3216 四套（~13KB）+ tfont12/16/24/32 汉字数组（~66KB）；pic.h = 演示位图 16.5KB；1.3 带字库版另有 `zk.c`（外置 SPI 字库芯片驱动，12KB）；1.8 另有 `HARDWARE\TOUCH\touch.c/h`（XPT2046，与 LCD 共用 SCLK/MOSI + 独立 TCS 片选）。

### 决策 A（拍板：六彩屏合并为单一 `lcd` 模块，运行时型号枚举——首选论证）

**对应关系**（目录 → wiki 页 → 芯片 → 分辨率，C8T6 例程 lcd_init.h 实测）：

| 厂家目录（caiping\） | wiki 页 | 芯片 | 分辨率（竖/横） | 例程默认方向 |
|---|---|---|---|---|
| 中景园ZJY096S0800TG01技术资料 | screen--0-96-color-screen.md | ST7735 | 80×160 / 160×80 | 横屏(2) |
| 中景园ZJY128S0800TG01技术资料 | screen--1-28-round-color-screen.md | GC9A01 | 240×240（圆屏） | 竖(0) |
| 中景园ZJY130S10Z0TG01技术资料 | screen--1-3-color-screen.md | ST7789V2（带字库版） | 240×240 | 竖(0) |
| 中景园ZJY147S0800TG01技术资料 | screen--1-47-color-screen.md | ST7789V3 | 172×320 / 320×172 | 横屏(2) |
| 中景园ZJY169S0800TG01技术资料 | screen--1-69-color-screen.md | ST7789V2 | 240×280 / 280×240 | 竖(0) |
| 中景园ZJY180S120TTG01技术资料 | screen--1-8-touch-color-screen.md | ST7735S + XPT2046 触摸 | 128×160 / 160×128 | 竖(1) |

**合并决策**：单 `lcd` 模块（仅 mspm0 条目），芯片差异 = 初始化序列 + 分辨率 + 偏移表（**厂家验证：lcd.c/字库/绘图层逐字节相同、只 lcd_init.c 不同**）。**芯片/屏型选择 = 运行时枚举**：`lcd_init(u8 model, u8 dir)`，model 取 `LCD_MODEL_096 / LCD_MODEL_128 / LCD_MODEL_130 / LCD_MODEL_147 / LCD_MODEL_169 / LCD_MODEL_180`（六模型常量，内部映射 5 种初始化序列：ST7735 / ST7735S / ST7789V2 / ST7789V3 / GC9A01 + 各自偏移表），dir 取 0-3（vendor USE_HORIZONTAL 语义）或 `LCD_DIR_DEFAULT`（=各屏例程原厂默认方向）。分辨率/偏移/方向态收敛为模块内静态（`lcd_get_width()`/`lcd_get_height()` 出参，不复用编译期 LCD_W/LCD_H 宏——lcd.c 不用该宏，仅用户 main.c 清屏用，改走 getter）。

**论证**（何为最优）：
1. **max7219 双形态合并先例**（同芯片同内核、形态差异 = 数据表/配置，用户代码选择）——本批六屏同构性更强（连 lcd.c 都逐字节相同），拆 6 份 = 6 份重复驱动 + wordlist 6 条互相干扰 + 同选逻辑重复；
2. **芯片/屏型是硬件事实而非题面事实**——题面说"屏幕"不报型号，AI 猜不准；运行时一行常量 = 唯一诚实接缝，用户按手中屏改一处；
3. **零生成器机制改动**——multi_instance 变体机制（led/key）语义是「通道宏 + 每通道脚」，与 lcd 的「静态 6 脚 + 一个型号常量」不匹配，硬套 = 选脚 UI 语义错乱 + 展开策略登记 + 渲染 hook + 骨架注入全套新代码，回归面大增；manifest 新 variants 字段同理（新字段 + 协议 + UI + 渲染，批次工作量 2-3 倍还叠机制成本）；
4. **flash 代价可忽略**——五套初始化序列 + 偏移表 ≈ 每套 <300B 只读数据；
5. "生成侧按题选芯片"落地 = 生成骨架接口块注入「型号常量 ↔ 屏型对照表 + 默认 0.96(ST7735, 打样件)」注释，LLM/用户按题面+实物选常量——不符合处（骨架默认值）由用户一眼可见可改，比静默写死一个生成侧猜测更稳。
6. **取舍记录**：若未来要"生成侧渲染 lcd_chip.h define"，需 manifest 变体字段 + 渲染 hook（可作后续批次，spec 记入范围外）。

**API 定稿**（对齐库内 oled 风格 + vendor 名规范化，slug 前缀 `lcd_`）：
- `lcd_init(u8 model, u8 dir)` / `lcd_get_width()` / `lcd_get_height()`
- `lcd_fill(x1,y1,x2,y2,color)` / `lcd_clear(color)` / `lcd_draw_point(x,y,color)` / `lcd_draw_line(x1,y1,x2,y2,color)` / `lcd_draw_rectangle(x1,y1,x2,y2,color)` / `lcd_draw_circle(x0,y0,r,color)`
- `lcd_show_char(x,y,chr,fc,bc,size,mode)`（size 12/16/24/32——ascii_1206/1608/2412/3216）/ `lcd_show_string(x,y,p,fc,bc,size,mode)` / `lcd_show_num(x,y,num,len,fc,bc,size)`（vendor ShowIntNum u16）/ `lcd_show_float(x,y,num,len,fc,bc,size)`（vendor ShowFloatNum1 固定 1 位小数）/ `lcd_show_chinese16x16(x,y,s,fc,bc,mode)`（s=GBK 双字节指针，遍历 tfont16 表——vendor LCD_ShowChinese16x16 形态；12/24/32 汉字尺寸不提供）/ `lcd_show_picture(x,y,w,h,pic)`（vendor LCD_ShowPicture 归一）
- 颜色宏保留 vendor 全套（WHITE/BLACK/RED/GREEN/BLUE/YELLOW/CYAN/MAGENTA/GRAY 等）

**字库策略（spec 定稿）**：`lcdfont.h` 保留 **ASCII 四套全留**（1206/1608/2412/3216 ≈ 13KB——12/16/24/32 四字号全可用，高频矢量集体积可控）+ **汉字仅保留 tfont16 常用集**（vendor 演示字符集，≈0.8KB；tfont12/24/32 汉字数组裁剪——24×N×72B、32×N×128B 为大头）+ **pic.h 不随库入库**（演示位图数据，用户自备，max7219 演示字模不入库先例；`lcd_show_picture` API 保留）；单文件目标 ≤ **16KB**（79KB → 16KB，生成工程不超时 + flash 省 8 倍）；字库体积断言写入测试。1.3 带字库版的 `zk.c`（外置 SPI 字库芯片）**不并入 lcd**——独立器件（SPI 字库芯片），未来独立模块/参考文件，notes 说明；lcd 汉字能力 = 内嵌 16x16 常用集。

**触摸（1.8）**：XPT2046 = **独立模块 `tp_xpt2046`**（可选依赖照 uwb_uart/filter 先例→但可选化未实现——本批就做**独立件**：用户按需单独选，与 lcd 并行、lcd 模块零触摸耦合；dependencies ["delay"]；软 SPI 4-5 脚 CS/CLK/DIN/DOUT/IRQ（IRQ 可选，轮询读坐标不注册中断——GROUP1 先例）；API = `xpt2046_init` + `xpt2046_read_xy(x,y)`（5 次中值滤波排序，vendor TP_Read_XY 归一）+ 坐标换算宏（校准系数出厂预设 Adujust=1，set_calibration 留接口）。

### 决策 B（拍板：扩展库内 `oled` 加 SPI 总线变体——零回归接口保留，首选论证）

0.96 SPI 单色屏（中景园电子ZJY096S0700WG01技术资料 → screen--0-96-single-spi-screen.md → SSD1306/SPI 128×64）——**扩展 oled 模块加总线变体**（用户推荐项；独立 oled_spi 条目 = 零回归但重复整份字库+驱动，照决策 A 论据不取）：
- **零回归接口**：现 `OLED_Init()`（I2C1 硬件 I2C 路径）与全部 `OLED_*`/`oled_*` 函数签名不动、I2C 路径代码不动；SPI 变体 = 新总线实现 + 新初始化函数 `OLED_SPI_Init(void)`（软 SPI 位操作 5 脚 SCL/SDA/DC/CS/RES——SSD1306 SPI 无 MISO；位操作照 nrf24l01/max7219 先例不占硬件 SPI 外设/TIMER）；`OLED_WR_Byte` 按模块内静态总线模式分发（I2C=现路径 / SPI=位操作路径），所有绘制/文本/显存函数共用——API 与显存语义（GRAM/Refresh）逐字节不变。
- **风险与回归**：动既有模块——本批必做 oled 全部测试回归（test_module_oled.py + 编译矩阵 I2C 变体重跑）+ 新增 SPI 变体测试；分支隔离（#if/静态模式）保证 I2C 路径零行为变化。
- **syscfg**：母版新增 GPIO 实例 `OLED_SPI`（5 脚全输出）。INSTANCE_CONSUMERS 加 `"OLED_SPI": ("oled",)`——oled 选中（任一总线）时两实例都保留：**已知取舍 = I2C1「OLED」实例的 PB2/PB3 默认脚在 SPI 模式下仍被占用**（不引入变体感知裁剪——机制成本 vs 低概率冲突权衡，SPI 模式下若需 PB2/PB3 经引脚绑定换脚消解，notes 记录；PB2/PB3 无其它模块默认占用，实测无撞车）。
- 剩余核对项（0.91 IIC / 0.96 IIC / 1.3 单色——ZJY091I0400WG01/ZJY096I0400WG01/ZJY130S0700WG01）：库内 oled 已覆盖（同 SSD1306 家族），**仅核对不提炼**；**0.91 = 128×32（SSD1306 半高）需核验 oled 是否支持**——库内 GRAM 为 [144][8]（128×64 全高），初始化 MUX/COM 按 64 行；若 0.91 不亮/回读异常 → 加分辨率宏 `OLED_RES_128X32`（MUX 0x1F + COM 0x22 + Refresh 只写 4 页，顺带回归）并记 spec/notes；若差异大（GRAM 布局不同）→ 记 notes 范围外（本批只补宏不重构）。

### 各件决策（顺序 = 用户建议顺序，含流水线演进）

| 工单 | 内容 | 母版 syscfg | 关键决策 |
|---|---|---|---|
| 01 | `lcd` 模块 + ST7735（0.96 打样）| 新 GPIO 实例 `LCD`（6 脚 SCL/SDA/RES/DC/CS/BLK 全输出，CS/BLK 初始 SET） | **全管线首件**：母版 syscfg 实例 + INSTANCE_CONSUMERS + wordlist「显示模块」一条 + test_module_lcd.py + 编译矩阵；API 定稿；字库裁剪定稿；默认脚定稿（见下） |
| 02 | lcd 补 ST7789V2（1.3 + 1.69）| 复用 LCD 实例 | 两屏同芯片但分辨率/偏移不同（240×240 vs 240×280）——各一条 model 表项；**核对字库策略**：1.3 带字库版外置字库芯片不入库（决策 A 已定），内嵌 16x16 常用集照常 |
| 03 | lcd 补 ST7789V3（1.47，172×320）| 复用 | 序号 2 后只需加 init 序列 + 偏移表项 |
| 04 | lcd 补 GC9A01（1.28 圆屏）| 复用 | 圆屏 = 全 240×240 无偏移 + 角上绘制越界由客户裁剪（驱动不裁，notes 说明） |
| 05 | lcd 补 ST7735S（1.8 屏体）| 复用 | 128×160；**触摸解耦**——本件不收触摸 |
| 06 | `tp_xpt2046` 独立模块 | 新 GPIO 实例 `TP_XPT2046`（CLK/DIN/DOUT 输出/输入 + CS + 可选 IRQ 输入） | 独立件（决策 A）；与 lcd 默认脚刻意错开（同屏幕接线共享 CLK/MOSI 是用户绑定选择，默认独立）；校准系数宏化（出厂预设，set_calibration 留接口） |
| 07 | oled SPI 总线变体（决策 B）| 新 GPIO 实例 `OLED_SPI`（5 脚） | 零回归接口 + OLED_SPI_Init；oled I2C 全量回归 + SPI 变体测试/矩阵；0.91 128×32 核验（不满足则补分辨率宏） |
| 08 | 收尾 | — | 全量测试 + 批次 1-12 全部 48 模块条目（≈53 件口径：六屏 6 件 + 触摸 + oled-SPI）一致性快检（sweep_48_modules.py）+ CONTEXT.md 平台行补录 + code-review（lcd 族抽 2 件深审 + 其余同构对仗核对）+ 中文提交 |

### 默认脚与重叠全景（原则 → 工单 01/06/07 定稿，test_pin_bindings 刻意重叠表登记）

- **原则**：31 IO 全占——新实例默认脚按「同选概率最低者与既有默认重叠」分配（max7219/IR_BEAM 先例）；**刻意不叠**：显示族（oled PB2/PB3、max7219 PB9/PA18/PB18、ws2812 PA14、led_beep PA15——彩屏与其它显示件同框罕见，且同选撞脚经绑定消解）、环境站（温湿度/光照/红外测温/粉尘——彩屏显示环境数据是常见组合）、板载键 PA2（彩屏+按键菜单 = 常见组合）。
- **LCD 六脚倾向**（工单 01 按重叠表落死，候选 = 语义互替件）：SCL←PA0（IR_TX 红外发射）、SDA←PA1（GP2Y1014 粉尘）、RES←PA12（FINGERPRINT 身份——输出互替）、DC←PA22（HUIDU 灰度/NRF IRQ/ZIGBEE——巡线车惯走 OLED，彩屏+8 路灰度不同框）、CS←PB19（JQ8900 语音）、BLK←PB20（SYN6288 语音——语音/显示互替）；同选经引脚绑定消解（六脚均可绑、`<实例>_<引脚>_PIN` 宏参数化）。
- **TP_XPT2046 五脚倾向**：与 LCD 六脚不同组（CS←PA8/CLK←PA13/DIN←PA16/DOUT←PA17/IRQ←PA27 档，工单 06 落死——触摸与增量编码/视觉/温湿度不同框）。
- **OLED_SPI 五脚倾向**：SCL←PA28/SDA←PA31/DC←PA15?（LED_BEEP 叠）……工单 07 落死（原则：与 oled I2C 的 PB2/PB3 错开、与显示族键脚错开、叠姿态/称重/身份低概率件）。

### 网盘依赖（本批无阻塞）

厂家例程已在本地（caiping\，工作区外只读）。wiki 页路径/原页/网盘链接/采购链接逐件从 `sources/materials/lckfb-地猛星移植手册/screen--*.md` 提取入 manifest notes（0-96 页：资料 https://pan.baidu.com/s/19DxY8JJEzNt4XYF_CwVbDw 提取码 8888）。

## 测试决策

照批次 1-11 先例逐件：

- `tests/test_pins.py`：MSPM0_DEFAULT_MAP 增 LCD/TP_XPT2046/OLED_SPI 实例默认脚（含刻意重叠对）；豁免元组若需（GPIO 位操作无 ADC 等 API 对偶——lcd/tp 无 adc 角色，先例豁免条件核对）。
- `tests/test_syscfg_prune.py`：LCD（lcd）/TP_XPT2046（tp_xpt2046）/OLED_SPI（oled）实例保留/裁剪断言。
- `tests/test_pin_bindings.py`：刻意重叠表登记（LCD 六脚 / TP 五脚 / OLED_SPI 五脚）。
- 新增 `tests/test_module_lcd.py`：manifest 形状（仅 mspm0 + 依赖 delay + 6 角色 gpio_out + 型号常量清单）+ 单选生成（syscfg 含 LCD 实例 + 模块文件落盘 + main.c 调 lcd_init/LCD_Show 系过静态门禁）+ **字库体积断言**（lcdfont.h ≤ 16KB + ascii_1608 存在 + tfont16 存在 + tfont24 汉字不存在 + pic.h 无）+ **无平台依赖守卫**（GPIO_ResetBits/RCC_/printf/DL_SPI 不得出现）+ 型号常量完整性守卫（6 模型常量齐全、每模型分辨率表）。
- 新增 `tests/test_module_tp_xpt2046.py`（同构：manifest + 单选生成 + 坐标读取函数门禁 + 无 IRQHandler 守卫）。
- `tests/test_module_oled.py` 回归（I2C 零变化）+ SPI 变体断言（OLED_SPI_Init 存在 + SPI 位操作无 DL_I2C 依赖 + 0.91 核验结论守卫）。
- wordlist.json 结构测试（lib_modules 挂接 lcd/tp_xpt2046 + models 词条）：新增后实测默认词表 wire 字节数，超 WORDLIST_PROMPT_BYTES=7300 fit 上限则按批次 5/7/8/9/11 先例上调并同步 budget.py/llm.py 记账。
- 编译级验收：每件复制 run_*_matrix.py 先例改 slug：单选生成 → SysConfig CLI 校验 → gmake 真编译（`C:/ti/ccs2050`）0 error 硬门槛、模块自身 warning 0；结果回写 manifest verified/notes。

## 范围外

- stm32 平台条目（仅 mspm0，批次 1 先例）、上板真机验证（未上板，notes 注明——SPI 时序/背光/偏移真机验证留后续）。
- 厂家例程硬件 SPI+DMA 版本（11-*例程，软 SPI 位操作为库规范）。
- 外置 SPI 字库芯片（zk.c，1.3 带字库版）——未来独立模块/参考文件。
- 24×24/32×32 汉字字库、pic.h 演示位图（裁剪对象，用户自备）。
- 电容触摸（1.8 例程为电阻 XPT2046；CT_MAX_TOUCH 电容协议页内无实现）。
- oled 0.91 若 GRAM 布局差异大需重构显存（仅承诺分辨率宏，见决策 B）。
- 「生成侧渲染 lcd_chip.h 变体 define」机制（决策 A 取舍记录，另行立项）。

## 补充说明

- 厂家源码 GBK 编码——提炼时按中景园 C8T6 例程（与 51/RC/ZET6 例程同源）取 `HARDWARE\LCD\` 六文件；`main.c` 演示（LCD_W/LCD_H 打印）不随库入库（骨架消费 getter）。
- 中文注释/编码：库内 C 文件 UTF-8（既有模块先例）；manifest notes 中文。
- wordlist「显示模块」一条：新 solution「IPS 彩屏（0.96/1.28/1.3/1.47/1.69/1.8 寸，ST7735/ST7789/GC9A01 系）含触摸选配件」lib_modules ["lcd","tp_xpt2046"]，models 增 ST7735/ST7789/GC9A01/XPT2046；note 写清六屏一模块 + 型号常量对照 + 打样推荐 0.96；另 OLED solution 补 SPI 总线变体说明（models 已有 OLED）。
- code-review 裁决（同构批量豁免逐件深审）：lcd 族抽 2 件深审（实现时随机种子定）+ 其余同构对仗核对；tp_xpt2046/oled-SPI 各 1 件深审。
- 完成后：全量测试 + CONTEXT.md 平台行补录（决策 A/B + 六屏六件 + 触摸 + oled-SPI 总线变体 + 默认脚全景）+ 中文提交（.githooks/commit-msg 强制中文；新增 .ps1 必须 UTF-8 with BOM）。
