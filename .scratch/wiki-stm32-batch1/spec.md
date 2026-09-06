# 批次 1「GPIO 迷你件打样」— 立创 wiki 地阔星 STM32F103C8T6 手册模块批量入库（stm32 线）

## 问题陈述

地猛星（MSPM0G3507）线已完成 70/70 页面全覆盖（批次 1-13，52 新 slug）；stm32 线现状 = 84 模块中仅 24 个有 stm32 平台条目（多为母版内嵌件），其余 60 个 mspm0 单平台件在 stm32 生成时全部报 missing 警告，用户做 STM32 工程时 AI 只能把这些模块当"需自备"。

地阔星 wiki（dkx-stm32f103c8t6）模块手册共 77 页（control 10 / rf 9 / screen 15 / sensor 43），已全量抓取至 `sources/materials/lckfb-地阔星移植手册/`（含模块索引/网盘索引/图片）。映射定稿（`.scratch/materials-wiki/dkx-map.tsv`）：A 类 61 件（库有 mspm0 条目、无 stm32 条目）、B 类 9 件（库无对应、新 slug，用户拍板**仅 stm32 条目**）、C 类 7 页 4 slug（已有 stm32，用户拍板**核对+补缺口**）。

本批 = **批次 1「GPIO 迷你件打样」**：6 件全为 GPIO 形态、无总线依赖、页面驱动 3-4 块、规模最小——用它们把 stm32 线管线（StdPeriph→ml_* 换算、pin_config.h 宏段、UV4 编译矩阵）完整打通，作为后 10 批的样板。layout 含：

| 件 | 页面 | 形态 | 备注 |
|---|---|---|---|
| relay | control--relay-module.md | gpio_out 1 脚 | 打样件；**F4 嫌疑页**（页面代码为 F4 口径，与 F103 矛盾，甄别样本） |
| flame | sensor--flame-sensor.md | gpio_in(+adc?) | |
| human_ir | sensor--human-body-infrared-sensor.md | gpio_in 1 脚 | |
| microwave_radar | sensor--microwave-doppler-radar-sensor.md | gpio_in 1 脚 | |
| ttp224 | sensor--ttp224-touch-sensor.md | gpio_in 4 脚 | |
| ws2812 | control--ws2812-color-rgb-led.md | gpio_out 位时序 1 脚 | 位时序打样件（忙等 + delay） |

## 方案

照地猛星批次 1-13 已确立管线，每件一个工单：手册「代码块」提炼完整驱动（正文内嵌段落禁用）→ 纯驱动切片改造（去 main/printf、API 规范化、ADR 0009 无状态机、页面 bug 人工复核修正+notes+守卫）→ **StdPeriph→母版 ml_* API 换算**（GPIO_Init→gpio_init、GPIO_SetBits/ResetBits/WriteBit→gpio_set、GPIO_ReadInputDataBit→gpio_get、delay_ms/us 同名；F4 口径页面按 F1 换算）→ 母版 `pin_config.h` 新宏段（尾形 `_GPIO/_PIN` 体系，pinwriter 8 尾形支持内）→ manifest stm32 条目（files/pins+macros/verified 初 false/kit+source_url=wiki 原页/notes 含手册路径+网盘+改造要点+修正记录）→ wordlist 补录 → 测试（新增 test_module_<slug>.py 照 test_module_ir_beam.py 模板 + test_pins/test_default_layout 同步）→ **UV4 单选编译矩阵 0 error/0 warning 硬门槛**（`C:/Keil5/Core/UV4/UV4.exe`，`-j0 -r -b`）→ verified 回写 → 中文提交 → 工单 resolved。

## 用户故事

1. 作为做题用户，我选 stm32 平台 + relay 后，生成工程打开即可编译，`relay_init()` + `relay_set(1/0)` 控制继电器吸合/断开（低压控高压，GPIO 宏化可绑任意脚）。
2. 作为做题用户，我选 stm32 + flame/human_ir/microwave_radar/ttp224/ws2812 后，对应 init + 服务函数可直接调用（状态检测/触摸读数/彩灯驱动），不再"需自备"。
3. 作为维护者，查看每个新条目能看到 stm32 平台条目（verified/kit/source_url=wiki 原页/notes 含手册路径+原页+网盘+换算要点+页面缺陷修正记录），可溯源到地阔星页面。

## 实现决策

### 既定事实（勿重新调研；本次调研实证，模块库现状读盘复核为准）

① **stm32 生成装配零新机制**：manifest `platforms.stm32.files` → `_copy_module_files`（generator.py:1975）→ KeilPatcher（keil.py:88 注册 modules 组 + IncludePath）；引脚 = `pins[].macros` → pin_config.h（pinwriter render_pin_config 行级覆写，尾形分派 `_stm32_macro_value` 8 种：`_EXTI/_LINE/_TIM/_CH/_UART/_INST/_PORT/_GPIO/_PIN/_Pin`）。

② **母版功能库 API 面**（ml_libs，部分 GBK 编码，读盘 errors=replace）：`gpio_init(GPIOn_enum,Pinx_enum,GPIO_MODE_enum)/gpio_set/gpio_get`（模式 OUT_PP/AF_PP/OUT_OD/IU/ID/IF/AIN；GPIO_A/B/C、Pin_0..15——PD 不可用）；软 I2C 原语 `I2C_Init/Start/Stop/SendByte/ReceiveByte/SendAck/NotSendAck/WaitAck`（ml_i2c，引脚宏 I2C_GPIO/I2C_SCL/SDA_GPIO_Pin 在 pin_config.h，SCL/SDA 同口约束）；ml_oled 独立软 I2C（OLED_GPIO/OLED_SCL/SDA_Pin，默认 PB8/PB9）；`ml_uart` UART_1/2/3（USART1/2/3，默认脚 PA9/10、PA2/3、PB10/11，`uart_pin_init_ex` 支持任意脚参数化）；`ml_pwm` TIM2/3/4 12 通道（TIM2_CH1..4=PA0-3、TIM3_CH1..4=PA6/7/PB0/1、TIM4_CH1..4=PB6-9，MAX_DUTY 50000）；`ml_adc` ADC1 通道 0-9（PA0-7/PB0-1 C8T6 可达；11-15 板无排针）；`ml_exti` EXTI_P{A,B,C}{0..15} 48 项（线号=脚 mod 16）；`ml_tim` TIM_2/3/4 `tim_interrupt_ms_init`；`ml_delay` delay_us/ms/s；`ml_systick` g_systick 1ms；`ml_led` led_init/on/off/toggle（led_instances.h 通道表）；**无 ml_spi、无硬件 I2C、无 TIM1**。

③ **板定义** `boards/stm32-min-system.json`：32 个 io 脚（PC13-15、PA0-7、PB0/1、PB10/11、PB9-3、PA15、PA12-8、PB15-12）；能力集 = 全部脚 `gpio_out/gpio_in/i2c_scl/i2c_sda/exti:PXn/enc:N` + pwm 12 脚 + adc 10 脚 + uart 6 脚（PA9/10、PA2/3、PB10/11）；fixed = 板载 LED PC13（低电平）、USB PA11/12、SWD PA13/14（板外弯针）、晶振 PD0/1、BOOT0/1。**无 spi_* 能力 token**——SPI 件全走软 SPI（gpio_out 角色），不改板文件。

④ **母版 pin_config.h 现状（32 脚全占用，无空闲）**：ADC_CH0/1=PA0/PA1、MOTOR_A/B_PWM(TIM2_CH1/2)=PA0/PA1、MOTOR_A_DIR/DIR2=PA6/PA7、MOTOR_B_DIR/DIR2=PB0/PB1、MOTOR_A_ENC=PB5(EXTI5)+dir PB4、MOTOR_B_ENC=PA4(EXTI4)+dir PA5、GRAY_D1-4=PB12-15、D5=PA8、D6=PB3、D7=PB6、D8=PB7、DIGIT/COORD/UWB(USART1)=PA9/PA10、DEBUG(USART2)=PA2/PA3、ZIGBEE(USART3)=PB10/PB11、LED=PC13/14/15、BUZZER=PA15、DIP=PB12-15、KEY=PB3、IR_BEAM=PA8、I2C=PA11/PA12(USB 共用)、OLED=PB8/PB9、SERVO(TIM4_CH1)=PB6。→ 新件默认脚 = 「同选概率最低」与既有默认重叠；重叠对登记 test_default_layout 白名单/刻意重叠表。

⑤ **默认脚重叠白名单现状**（tests/test_default_layout.py 4 组残留）：DIP0-3×GRAY_D1-4(PB12-15)、KEY×GRAY_D6(PB3)、ADC_CH0/1×MOTOR_A/B_PWM(PA0/1)、SERVO_PWM×GRAY_D7(PB6)、IR_BEAM×GRAY_D5(PA8)。

⑥ **编译矩阵**：stm32 无 SysConfig/makefile；`compile_runner.collect_build_log` stm32 分支 = `UV4.exe -j0 -r -b <uvprojx> -o <临时log>`；`compile_passed` exit 0（无错无警）/1（有警无错）都算过、2=错——**本线硬门槛 = exit 0 且模块自身 warning 0**；本机 C:/Keil5/Core/UV4/UV4.exe 实测存在（ARMCC V5.06u7，C:/Keil5/Core/ARM/ARMCC/Bin）；先例 `.scratch/module-polish/compile_matrix.py`（2026-08-15 19 模块全 PASS）+ `ir-beam-module/01` 单模块矩阵（2026-09-05）。

⑦ **测试接缝（stm32 侧，区别于 mspm0）**：test_pins.py **无 STM32_DEFAULT_MAP**——替代 = `STM32_MACRO_VALUES`（宏名→现值表）+ `test_stm32_declaration_macros_exist_in_master_headers`（声明 macros 必须真实存在于母版头）+ `test_every_declaration_default_on_board_and_capable`（默认脚必须在板定义且能力合法）+ `test_module_code_has_no_pin_literals`（零 PA*/Pin_*/UART_*/USART*/EXTI_*/TIM*/ADC_Channel 字面量；注释/字符串豁免）。模块测试模板 = `test_module_ir_beam.py`（manifest 形状 + 母版宏存在断言 + 单选生成全流程断言）。

⑧ **页面代码通性**：地阔星页面 = STM32 F1/F4 标准外设库 + 立创壳（board.h→board_init、bsp_uart.h→uart1_init、printf 走 uart1、delay_ms/us 同名）；第三代码块 = 演示 main（board_init+uart1_init+while(1)+printf，全部剔除）；页面间有「与 DHT11 相同」指引句（零信息，不提炼）；网盘链接每页 1-5 条随 notes；**F4 嫌疑 6 页**（本批 relay 命中：`RCC_AHB1PeriphClockCmd`/`GPIO_OType`/`stm32f4xx.h`——按 F1 换算表逐行翻译）。

⑨ **页面 bug 修正目录**（照地猛星 23 类，逐页检查）：NACK 缺查/重试条件写反/极性宏与正文矛盾/注释与函数名不符/位序/缓冲回绕/类型宽度/模板注释残留/演示数据混入/返回码与合法值冲突……修正 = 人工复核+notes+测试守卫。

⑩ **来源标注**：新 stm32 条目 `source_url` = 地阔星 wiki 原页（`WIKI_SOURCE_URL_PREFIX` 前缀命中，lckfb-attribution 判据）；notes 记手册路径（`sources/materials/lckfb-地阔星移植手册/<cat>--<slug>.md`）+ 原页 + 网盘链接 + 采购链接 + 换算/修正要点；kit = 页面「模块来源」套件名。

⑪ **B 类仅 stm32 条目**（用户拍板）：mspm0 缺条目 = missing 警告（镜像「仅 mspm0」先例），本批无 B 类件。

⑫ **C 类核对+补缺口**（用户拍板）：本批无 C 类件（servo/motor/ml_mpu6050/oled 在批次 11 收官处理）。

### 共性（六件一致）

1. **仅 stm32 条目**（本批全是 A 类：mspm0 条目已存在，不新增/不改写 mspm0 侧）；`verified` 初始 false，UV4 矩阵 0/0 过 → true；`hardware_bound: false`；未上板（notes 注明）。
2. **代码提炼**：手册「代码块」抽 bsp_xxx.c/.h（正文内嵌段落禁用）→ `xxx_init()` + 服务函数（API 与 mspm0 版对齐：同函数名/同语义）；去 main/printf/board_init/uart1_init；函数名规范化（`Set_Relay_Switch`→`relay_set` 级）；全局收敛模块内静态 + 出参；ADR 0009 无状态机。
3. **换算**：StdPeriph → 母版 ml_* API（换算映射表见各件决策）；F4 口径行按 F1 换算表翻译（RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOx)→RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOx)；GPIO_Mode_OUT+GPIO_OType_PP+GPIO_PuPd_UP→GPIO_Mode_Out_PP；GPIO_Speed_100MHz→GPIO_Speed_50MHz；GPIO_WriteBit 同名）；**模块内不出现任何寄存器级/标准库调用**，只吃 ml_* API + pin_config.h 宏。
4. **引脚宏参数化**：manifest pins（id/type/default/required/macros——macros 指向 pin_config.h 新增宏 `_GPIO/_PIN` 尾形）；模块 .c/.h 零引脚字面量（测试门禁）；默认脚按「同选概率最低」与既有默认重叠（见各件决策与重叠全景），重叠对登记 test_default_layout 白名单（或刻意重叠表）。
5. **极性归一化**：模块 .h 暴露单宏（RELAY_ON_LEVEL/TTP224_TOUCH_LEVEL/HUMAN_IR_TRIGGER_LEVEL/MICROWAVE_TRIGGER_LEVEL 先例），语义 = 用户直觉（1=吸合/1=检测到/1=触摸），页面反义经 `1−s` 对照注释入 notes。
6. **时序**：延时全走 delay 模块（dependencies ["delay"]；ws2812 位时序忙等）；不占 TIMER；不注册 GPIO 中断（轮询）。
7. **wordlist 补录**：relay/flame/human_ir/microwave_radar/ttp224 就近分类（执行机构/感知传感器/触控输入）、ws2812（显示模块）——补录时实测词表预算链。

### 各件决策（2026-09 回填，页内事实已取证）

| 工单 | slug | 手册 | 形态 | 母版 pin_config.h 宏段 | 关键决策 |
|---|---|---|---|---|---|
| 01 | relay | control--relay-module.md（**F4 页**） | gpio_out 1 脚 | `RELAY_GPIO/RELAY_PIN` | API = `relay_init()`（初始断开）+ `relay_set(uint8_t)`（1=吸合/0=断开；页面 `Set_Relay_Switch` 0=吸合/1=断开 → `Set_Relay_Switch(s) ≡ relay_set(1-s)` 对照注释）；`RELAY_ON_LEVEL 0u`（低电平吸合=页面模块）；**F4→F1 换算**（RCC_AHB1PeriphClockCmd→RCC_APB2PeriphClockCmd、GPIO_Mode_OUT+OType_PP+PuPd+Speed_100MHz→GPIO_Mode_Out_PP+Speed_50MHz、GPIO_WriteBit 同名——页面整页 F4 口径与 F103 标题矛盾，疑似 F4 板页复制未迁移，notes 甄别记录）；页面默认脚 PA2 **不采用**（DEBUG TX——pin_config.h 现状 PA2 = DEBUG_UART TX，spec 笔误更正）；默认 OUT=**PB4**（叠 MOTOR_A_ENC_DIR——继电器与编码器闭环车不同框；刻意不叠声光/执行件） |
| 02 | flame | sensor--flame-sensor.md（F1） | ADC 通道 + DO 未声明 | `FLAME_AO_CH` | API = `flame_init()`（adc 模块通道初始化，依赖 ["adc"]）+ `flame_read_percent()`（5 次快平均 + 反向映射 `(1-value/4095)×100`——页面原式，红外越强 ADC 越小百分比越高；相对强度非绝对值）；页面默认 AO=**PA5**（ADC1_CH5）/DO=PA6——**DO 未用不声明**（LM393 阈值由可调电阻控制，mspm0 先例）；**页面缺陷清单**：`delay_1ms(20)`（ml_delay 无 delay_1ms→delay_ms(20)）、`%d` 打 unsigned int（演示剔除）、SAMPLES 30×25ms 过慢（改 5 次快平均）；默认 AO=**PA5**（=页面原脚；独立通道 ADC_Channel_5——与 adc 模块 CH0/1 不共读（mspm0 独立 MEM6 语义同构）；PA5 叠 MOTOR_B_ENC_DIR——火焰与编码器闭环不同框；同选经绑定消解） |
| 03 | human_ir | sensor--human-body-infrared-sensor.md（F1） | gpio_in 1 脚 | `HUMAN_IR_GPIO/HUMAN_IR_PIN` | API = `human_ir_init()`（空占位，IU 上拉输入）+ `human_ir_read()`（1=感应到）；**极性缺陷（定论）**：页面 L102 注释「0=感应到」与正文/规格「输出高」矛盾、代码 L108 实际高=1——按器件规格「高=感应到」修正，`HUMAN_IR_TRIGGER_LEVEL 1u`，notes 记（mspm0 同款修正先例）；轮询不注册 EXTI；默认 OUT=**PB7**（叠 GRAY_D8——人体红外与巡线车不同框；避让声光/按键/门禁组合） |
| 04 | microwave_radar | sensor--microwave-doppler-radar-sensor.md（F1） | gpio_in 1 脚 | `MICROWAVE_GPIO/MICROWAVE_PIN` | API = `microwave_radar_init()`（IU 上拉输入）+ `microwave_radar_read()`（1=检测到；`MICROWAVE_TRIGGER_LEVEL 0u`——RCWL-0516 低有效脉冲，mspm0 同款；页面/代码/演示自洽、正文未声明极性、未上板——notes）；页面宏 `RCC_OUT/OUT_IN` 无前缀撞名风险 → 本件宏统一 `MICROWAVE_` 前缀；型号 mh100x vs 采购 HB100 命名不一致（记录不裁决）；页面默认 PA1 **弃用**（叠 adc ADC_CH1+MOTOR_B_PWM 常备件）→ 默认 OUT=**PA4**（叠 MOTOR_B_ENC EXTI4——微波与编码器闭环不同框；轮询不注册 EXTI） |
| 05 | ttp224 | sensor--ttp224-touch-sensor.md（F1） | gpio_in 4 脚 | `TTP224_GPIO`+`TTP224_OUT1..4_PIN` | API = `ttp224_init()` + `ttp224_read(channel 1-4)` + `ttp224_read_all()`（低 4 位掩码）；`TTP224_TOUCH_LEVEL 1u`；页面原式 **IPD 下拉输入**（mspm0 为 IU——差异无碍，notes 记录；触摸=高电平自洽）；页面 4 个 Key_INx_Scanf 收敛 read/read_all；默认 OUT1-4=**PB12/13/14/15**（叠 DIP0-3+GRAY_D1-4——触摸与拨码/巡线不同框；四脚同口共享 TTP224_GPIO 宏，换口须整组迁移） |
| 06 | ws2812 | control--ws2812-color-rgb-led.md（F1） | gpio_out 位时序 1 脚 | `WS2812_GPIO/WS2812_PIN` | API 与 mspm0 全同（init/set_led_count/led_count/set_color(0xRRGGBB)/set_rgb/refresh；WS2812_MAX 8；GRB 缓冲序在 set_color 换位——页面颜色序正确）；**页面缺陷清单（4 条，全部 notes+守卫）**：① 延时循环 `for(k=0;i<0;i++);` 条件写反 ×4（0 次迭代脉宽全丢，照抄灯不亮）② `LedId > ledsCount` 越界 → `>=`（写 LedsArray[24..26]）③ 时序按 12MHz 标注（NOP×5≈69ns）而工程 72MHz——页面脉宽标注作废，按 mspm0 口径重写（位1≈1us+0.25us 换算）④ .h 声明 setLedCount/getLedCount/RGB_LED_Write1 无定义（上游残留，不声明）；800kHz 位时序忙等（delay_us(1)+0.25us 换算，照 mspm0 ws2812.c 结构；不占 TIM/PWM、不注册中断），依赖 ["delay"]；页面默认 PB12 **不采用**（本批 ttp224+DIP/GRAY 已占）→ 默认 DIN=**PA8**（叠 IR_BEAM+GRAY_D5——彩灯与红外对射/巡线不同框；刻意不叠灯族） |

### 默认脚与重叠全景（定稿）

| slug | 默认脚 | 重叠主体（同选概率最低） |
|---|---|---|
| `relay` | OUT=PB4 | MOTOR_A_ENC_DIR（编码器闭环——不同框；刻意不叠声光/执行件：LED/BUZZER/电机 PWM/方向） |
| `flame` | AO=PA5 | MOTOR_B_ENC_DIR（编码器方向输入——独立 ADC 通道、页面原脚；火焰≠编码器闭环） |
| `human_ir` | OUT=PB7 | GRAY_D8（pid 巡线第 8 路——不同框；避让声光/按键/门禁组合：BUZZER/KEY/SERVO） |
| `microwave_radar` | OUT=PA4 | MOTOR_B_ENC（EXTI4 光电编码器——不同框；页面默认 PA1 弃用） |
| `ttp224` | OUT1-4=PB12/13/14/15 | DIP0-3 + GRAY_D1-4（拨码配置/巡线——不同框；四脚同口） |
| `ws2812` | DIN=PA8 | IR_BEAM + GRAY_D5（对射/巡线——不同框；页面默认 PB12 弃用；刻意不叠灯族） |

- **六件默认互不相撞**（PB4/PA1/PB7/PA4/PB12-15/PA8 全异）；重叠对全部登记 test_default_layout.py 白名单（stm32 段）+ 注释理由/批次号。
- 与既有默认重叠计数（test_default_layout 白名单）：PB4 +1（relay）、**PA5 +1（flame）**、PB7 +1（human_ir）、PA4 +1（microwave_radar）、PB12-15 +4（ttp224）、PA8 +1（ws2812）。
- 消解机制：同选经引脚绑定换脚（pinwriter 渲染 `_GPIO/_PIN` 宏；ttp224 四脚同口约束需整组迁移——共享端口宏异值 400）。**页面默认脚全部不照抄**（互抢 PA1-6/PB12 且全中既有占用——研究报告跨页脚位冲突节；F103C8T6 实际空闲仅 PB2 未引出）。

## 测试决策

- 新增 `tests/test_module_relay.py` / `test_module_flame.py` / `test_module_human_ir.py` / `test_module_microwave_radar.py` / `test_module_ttp224.py` / `test_module_ws2812.py`（照 test_module_ir_beam.py 模板）：
  1. manifest 形状：platforms 含 stm32（mspm0 条目原样保留）、files 逐个存在、pins 元组 (id,type,default,required,macros)、kit+source_url=wiki 原页、notes 关键子串（手册路径/网盘/F4 换算记录/修正记录）。
  2. 母版宏存在断言：pin_config.h `#define <MACRO>\s+<值>` 正则（STM32_MACRO_VALUES 若有钉值新增/同步）。
  3. **stm32 单选生成全流程**：resolve_selection + generate → `modules/<slug>/code/*.c` 落盘 + `.uvprojx` modules 组含 .c + pin_config.h 在工程根（照 test_module_ir_beam.py::test_ir_beam_stm32_single_select_generation）。
  4. 关键守卫：无 `printf`/`main`/`board_init`/`GPIO_Init`/`RCC_`/`stm32f10x.h`/`stm32f4xx.h` 字面量、极性宏值与对照注释、页面缺陷防回潮（按各件列）、零引脚字面量（全库门禁自动覆盖）。
- `tests/test_pins.py`：`test_stm32_declaration_macros_exist_in_master_headers` 自动覆盖新 macros；`STM32_MACRO_VALUES` 若需钉值（relay 等新宏）补表项；`test_every_declaration_default_on_board_and_capable` 覆盖默认脚合法性。
- `tests/test_default_layout.py` 白名单：新默认脚重叠对登记（若不可避免）。
- **UV4 编译矩阵**（每件）：复制 .scratch/wiki-modules-batch13/run_<slug>_matrix.py 改 slug（stm32 版：resolve_selection → generate → collect_build_log(uv4=find_uv4()) → compile_passed exit 0 + 模块 warning 0）→ 产物 .scratch/wiki-stm32-batch1/matrix/<slug>/。MAIN_C 调 init+全部服务函数（(void) 化）。
- 词表预算链：六件补录后实测 wire（现状含 stm32 词？wordlist 无平台字段——补录与地猛星批同口径），超限按先例上调 WORDLIST_PROMPT_BYTES 并同步 REFERENCE_FULLTEXT_BYTES/budget.py/llm.py 记账；test_llm 结构测试不截断契约保持绿。

## 范围外

- mspm0 条目改动（本批 A 类仅补 stm32；mspm0 侧零改动）；B 类新模块（批次 4/7/9/10/11）；C 类核对（批次 11）。
- 上板真机验证（未上板，notes 注明——继电器吸合时序/人体红外阈值/WS2812 时序精度真机验证留后续）。
- 页面「与 DHT11 相同」指引句不提炼；演示 main 不提炼；页面未实现的寄存器族/模式（如 WS2812 双缓冲/流灯）notes 说明。
- 硬件 SPI/新增 ml_spi（板无 spi token、库无 ml_spi——SPI 件软 SPI，本批无 SPI 件）。
- 母版 ml_libs 改动（本批无；oled SPI 变体属批次 11 C 类补缺口）。
- fputc/printf 接线（依赖 debug_uart/config 模块，生成时按骨架）。

## 补充说明

- 排序：01 relay（打样件：F4 甄别 + 极性宏 + 初始断开）→ 02 human_ir → 03 microwave_radar（迷你件练手）→ 04 flame（+ADC 判定）→ 05 ttp224（4 脚输入）→ 06 ws2812（位时序打样，最重）。
- 页内事实（代码块结构/F1/F4/极性/缺陷/API 对照）= 研究子代理 ddb09feb 报告（%TEMP%\batch1-facts.md，2026-09 已回填 spec 决策表 + 工单 02/03/06 修订：flame 默认 PA5 独立通道、human_ir 极性缺陷定论、ws2812 页面缺陷 4 条）。
- **code-review 两轴结果（2026-09-06 收尾）**：Standards 轴（子代理报告）——**0 硬违反**（ADR 0009/0010/0005 溯源、先例同构（API 同名同语义/极性宏放 .h/static 收敛/include 顺序）、manifest 纯增量 mspm0 零改动全部通过）；判断项 3 条：① 测试 BANNED_CODE_PATTERNS/MAIN_C_STM32 常量 6 文件复制（延续 ir_beam 单文件自包含先例，可接受）② ttp224_raw_level 4-case switch 与 mspm0 版同构（跨平台成对文件既定模式）③ ws2812 位时序经函数调用开销实际 ~1.4us/位（0.25us 脉宽精度存疑）——按 spec/notes「真机验证非编译级」处理，仅提示；另转 spec 轴 2 项已处理：ws2812 词表挂「感知传感器」组（mspm0 批历史分类，spec 决策 7「显示模块」未迁移——工单 06 记录为词表维护项，本批零手动迁移以防预算链噪音，批次 11 词表整卷重排教训；若迁移需同步预算实测）、spec 决策表 relay 行「DEBUG RX」笔误→已改「DEBUG TX」（实现与 pin_config.h 均正确）。Spec 轴（子代理超时中断，主代理自查补位）——spec 验收点全闭环：① 六件 manifest stm32 条目字段（files/pins+macros/source_url=dkx 原页/notes 手册路径+网盘+换算修正记录/verified true/hardware_bound false）② 模块代码纯 ml_* API+宏、零字面量（门禁）③ 默认脚与 test_default_layout 白名单全登记④ 页面 bug 修正与 notes（human_ir 极性修正/flame 三处/ttp224 IPD 原式/ws2812 缺陷 4 条/relay F4 甄别）⑤ UV4 矩阵 6/6 PASS→verified=true ⑥ 12 条中文提交 ⑦ 收尾（pytest 3601 + node 1359 全绿、sweep_6_modules 6/6 OK、CONTEXT.md 平台行补录）⑧ 词表零补录（mspm0 口径）。
- 收尾清单（全批完成）：全量 pytest + node:test → 一致性快检（照 sweep_52_modules.py 更新，stm32 线版：stm32 条目存在性/verified/hardware_bound/wordlist 挂接/source_url wiki 判据/依赖正检）→ code-review 两轴 → CONTEXT.md 平台行补录（stm32 线批次 1 块）→ 中文提交。
