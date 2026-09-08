# 批次 7「测距/输入件」— 立创 wiki 地阔星 STM32F103C8T6 手册模块批量入库（stm32 线）

## 问题陈述

stm32 线进度：批次 1-6 已入库 40 件（全部 0/0 矩阵）。本批 = **测距/输入件**：us016、ir_distance（ADC 测距——A 类，互替件）、joystick（双轴 ADC + SW——A 类）、ec11（**B 类新 slug —— 库内无旋转编码器模块**）、key_matrix（**B 类新 slug —— 4×4 矩阵键盘**）。B 类两件 = 仅 stm32 条目（用户拍板口径），无 mspm0 对照，从零设计（相近件参考：motor 编码器 / key 独立按键 / ntb_time）。

## 方案

照批次 1-6 管线；ADC 件按批 5 模式（`<SLUG>_AO_CH` 宏 + adc_init/adc_get + 5 次快平均 + 默认通道共读/share 组白名单）；ec11/key_matrix 按 B 类设计（轮询优先、宏族单源、防抖归调用方）。每件：提炼 → 纯驱动切片 → 换算 ml_* → pin_config.h 宏段 → manifest → 测试 → UV4 矩阵 0/0 → verified → 中文提交。

## 用户故事

1. 做题用户选 stm32 + us016/ir_distance：`init()+read_distance_cm()` 直接出距离（us016 0.75 系数、ir_distance 3.3V 宏化+20-150cm 曲线——**函数名与 mspm0 完全同名**）。
2. 做题用户选 stm32 + joystick：`read_x_percent/read_y_percent/read_sw()` 直接出双轴百分比+按击（4 次快平均+忙等超时）。
3. 做题用户选 stm32 + ec11：`ec11_init()/ec11_get_delta()/ec11_read_sw()` 旋钮步进+方向+按键（轮询，不占 TIM/EXTI）。
4. 做题用户选 stm32 + key_matrix：`key_matrix_init()/key_matrix_scan()` 0-16 键值（4 行输出+4 列输入 8 脚宏族，防抖归调用方节拍）。
5. 维护者：每件可溯源（source_url=wiki 原页；B 类 notes 注明无 mspm0 条目/设计依据）。

## 实现决策

### 既定事实（勿重新调研；batch7-facts.md 已取证，5 页全 F1 零 F4）

① **us016**：默认 AO=PA5（页面原脚=共读点）；换算 `L=A×0.75mm`（=3072/4096——正文 L49「3096」与代码/注释「3072」不一致，mspm0 批 2 按代码 0.75 定稿；main /10 出 cm——**出参 cm（float）**）；50 次×10ms=500ms 阻塞采样 → 5 次快平均。
② **ir_distance**：默认 AO=PA5（与 us016 **互替件**同脚——同选经绑定换 PA0/PA1）；换算 `V=raw/4095×3.3`（**页面硬编码 3.5V，mspm0 已改 3.3 宏化**——3.3V 供电下页面换算系统偏低约 6%）、`Distance=60.374×V^(-1.16)` cm（20-150cm 段；<15cm 电压跌落非线性区——notes）；出参 cm（float：`ir_distance_read_cm()`——mspm0 API 签名以库内为准）；页面 L44「下图曲线图」实为 0 图（无查表——按公式）。
③ **joystick**：页面默认 VRX=PA1/VRY=PA2/SW=PA3（全被既有角色占用，不照抄）→ **X=PA1（ADC_Channel_1，与 adc 模块 ADC_CH1 共享组）/Y=PA0（ADC_Channel_0，与 adc 模块 ADC_CH0 共享组）/SW=PA10（gpio_in——叠 DIGIT/COORD/UWB UART RX——摇杆与视觉/数传不同框，mspm0 SW=PA9 同款推理）**；换算 `(adc/4095)×100`、SW 低有效（0=按下）、中心≈50%；**L149 注释函数名「Get_MQ2_Percentage_value」MQ2 串台**（notes）；每次 30×2ms=60ms + 2 次 ADC 校准无超时 → 4 次快平均+忙等超时（mspm0 先例）。
④ **ec11（B 类）**：页面默认 A=PA6/B=PA4/SW=PA7（全占不照抄）→ **A=PA4/B=PB5/SW=PB0**（推理：EC11 人机旋钮与「微波雷达（PA4）+称重（PB5/PB0）+光电编码器闭环」不同框；刻意不叠人机面板组合件（KEY/OLED/数码管——旋钮+屏幕/按键面板标配）与声光件）；解码 = **默认轮询 A/B 相**（A 相跳变采样 B 相判向——页面算法；**非 EXTI**——避开 `_check_exti_line_conflicts` 异口同线门禁、不占 TIMER（页面 TIM3 中断扫描消抖改为轮询+防抖归调用方——PCB 页面 L60-61 真值表与正文 L44-46、代码 L157-189 判向矛盾，按代码（A 相跳变采样 B）为准+notes）；printf 在驱动文件内（剔除）；SW=100ms 阻塞消抖→防抖归调用方节拍）；API = `ec11_init()/ec11_get_delta()/ec11_read_sw()`（get_delta = 返回自上次清零的方向+步数增量（正=顺时针/负=逆时针，页面计数语义归一）——题目常用「旋转 N 格」）。
⑤ **key_matrix（B 类）**：页面行列全 GPIOA（行输出=PA7-4 低有效、列输入=PA3-0 上拉——全占不照抄）→ **ROW1-4=PB12/13/14/15（叠 DIP0-3+GRAY_D1-4+ttp224——互替件同脚先例（open_mv4×digit_uart）：机械键盘×触摸 4 键互替、同选概率最低、同脚经绑定消解）+ COL1-4=PA9/PA10/PB10/PB11（叠 DIGIT/COORD/UWB UART + ZIGBEE UART——键盘与视觉/数传链路不同框）**；扫描 = 逐行拉低扫列（页面原式），键值 `i×4+j+1`（0-16 行主序）；无防抖/连按/释放语义——**防抖归调用方节拍**（key 模块先例）；L22「bsp_mh100x.c」vs L39 include 串台（notes）；main 500ms 演示节拍会丢键（不落）；API = `key_matrix_init()/key_matrix_scan()`（uint8 0-16）。
⑥ **B 类口径**：仅 stm32 条目（mspm0 缺条目标 missing）；notes 注明「无 mspm0 条目（地阔星仅有页面）——B 类拍板（仅 stm32）」。

### 各件决策

| 工单 | slug | 类型 | 默认脚 | API（与 mspm0 对齐/B 类设计） | 修正/notes |
|---|---|---|---|---|---|
| 01 | us016 | A | AO=PA5 | `us016_init()/us016_read_distance_cm()`（float；**与 mspm0 同名（us016.h L30）**；`US016_ADC_SAMPLES 5` + **双量程宏 `US016_RANGE_1M`（0→0.25 档/1→0.75 档，默认 0）**） | 3096/3072 按代码 0.75（1m 档）；500ms→5 次快平均；DO 按 mspm0 现状 |
| 02 | ir_distance | A | AO=PA5 | `ir_distance_init()/ir_distance_read_distance_cm()`（float；**与 mspm0 同名（ir_distance.h L21）**；**`IR_DIST_ADC_SAMPLES 10`（宏名照 mspm0，值 10=手册原值）**；3.3V 宏化；60.374×V^-1.16） | 3.5→3.3 宏化；**页面 30 次→10 次（非 5）**；无查表；互替 us016 notes；<15cm 非线性 notes |
| 03 | joystick | A | X=PA1/Y=PA0/SW=PA10 | `joystick_init()/joystick_read_x()/read_y()`（uint16_t 原始值）+ `read_x_percent()/read_y_percent()`（**uint16_t 整数 0-100%**——mspm0 joystick.h L29-30 同名同型）/`read_sw()`（`JOYSTICK_SW_PRESSED_LEVEL 0` 沿名） | MQ2 串台注释；60ms→4 次快平均+忙等超时；SW 低有效 |
| 04 | ec11 | **B** | A=PA4/B=PB5/SW=PB0 | `ec11_init()/ec11_get_delta()/ec11_read_sw()` | 页面真值表/代码判向矛盾按代码；TIM3 中断改轮询；printf 剔除；SW 防抖归调用方 |
| 05 | key_matrix | **B** | ROW1-4=PB12-15 / COL1-4=PA9/PA10/PB10/PB11 | `key_matrix_init()/key_matrix_scan()`（0-16） | bsp_mh100x 串台；防抖归调用方；8 脚宏族 |

### 默认脚与重叠全景（定稿）

| slug | 默认脚 | 重叠主体（同选概率最低） |
|---|---|---|
| us016 | AO=PA5 | flame+批 5 件（**ADC 共享组**，互替 us016×ir_distance 同脚=互替同脚先例；物理约束 notes） |
| ir_distance | AO=PA5 | 同上（互替件同脚；同选经绑定换 PA0/PA1） |
| joystick | X=PA1 / Y=PA0 / SW=PA10 | adc 模块 ADC_CH1/CH0（**ADC 共享组**）+ DIGIT/COORD/UWB UART RX（摇杆与视觉/数传不同框；mspm0 SW=PA9 同款推理） |
| ec11 | A=PA4 / B=PB5 / SW=PB0 | microwave/MOTOR_B_ENC（A）+ hx711 SCK/MOTOR_A_ENC（B）+ hx711 DT（SW）——EC11 人机旋钮与微波/称重/光电编码器闭环不同框；刻意不叠人机面板组合（KEY/OLED/数码管）与声光 |
| key_matrix | ROW=PB12-15 / COL=PA9,PA10,PB10,PB11 | DIP0-3+GRAY_D1-4+ttp224（ROW——互替件同脚先例）+ DIGIT/COORD/UWB、ZIGBEE UART（COL——键盘与视觉/数传不同框） |

- 白名单登记：PA5 组 +2（us016/ir_distance——ADC 共享组）、PA1/PA0 +1×2（joystick X/Y——adc 共享组）、PA10 +1（joystick SW）、PA4 +1 / PB5 +1 / PB0 +1（ec11 三脚）、PB12-15 +4（key_matrix ROW——ttp224 同脚组）、PA9/PA10/PB10/PB11 +4（key_matrix COL——注 PA10 与 joystick SW 并列登记）。
- **同选消解**：全部同选经引脚绑定换脚（pinwriter 行级覆写）；互替件（us016×ir_distance、key_matrix×ttp224）同脚为「互替同脚先例」语义（二选一接入，无需另消解）。

## 测试决策

- `tests/test_module_us016.py` / `test_module_ir_distance.py` / `test_module_joystick.py`（照批 5 test_module_mq2.py 模板：形状+宏存在+单选生成全流程+mspm0 零改动守卫+守卫）：
  - us016：`US016_ADC_SAMPLES 5` + `US016_RANGE_1M 0` + `0.25f/0.75f` 双档（页面 3072 口径）、出参 cm 注释、无 500ms 式；
  - ir_distance：`3.3f`（**无 3.5f**）、`60.374f`、`-1.16f`、**`IR_DIST_ADC_SAMPLES 10`（宏名无 ANCE、值 10——防回写成 5）**、无查表（数组）；
  - joystick：**API 全套 6 函数（init/read_x/read_y/read_x_percent/read_y_percent/read_sw——raw 与 percent 均 uint16_t）**、SW 低有效注释、4 次快平均（`JOYSTICK_ADC_SAMPLES 4u`——mspm0 口径）、无 MQ2 字面量。
- `tests/test_module_ec11.py`（B 类模板新）：manifest（**仅 platforms.stm32**/files/pins 3 行/macros/source_url wiki 原页/notes 子串「B 类」「无 mspm0」）+ 宏存在（`EC11_A_GPIO\s+GPIO_A`/`EC11_A_PIN\s+Pin_4`/B/SW 同款）+ 单选生成全流程（**生成平台 stm32 单选**——mspm0 生成报 missing 警告断言？照 B 类口径：stm32 单选绿+守卫（轮询——无 EXTI/NVIC/TIM、get_delta 增量语义、"A 相跳变采样 B" 判向注释）+**EXTI 门禁不触发**（默认脚 PA4/PB5/PB0 线号：4/5/0——异口同线? PB5 线 5 与 MOTOR_A_ENC（线 5）=同线同脚? PA4 线 4/MOTOR_B_ENC 同脚——**注意**：ec11 默认脚与既有 ENC 角色同脚——EXTI 门禁只查「用户绑定改动」——默认组合不拦（现状口径），但 EC11+电机同选时经绑定；门禁无碍）。
- `tests/test_module_key_matrix.py`：形状（8 pins/macros 8 组——ROW 共享 `KEY_MATRIX_ROW_GPIO`? 按 page 行列宏族——**4 行 4 列共端口**（页面全 GPIOA）——宏设计：`KEY_MATRIX_GPIO` 单端口宏 + `ROW1..4_PIN` + `COL1..4_PIN` 10 宏（共享端口宏同值约束同口——**注意：默认 ROW 在 PB12-15、COL 在 PA9/10/PB10/11 = 跨端口！**→ 逐脚宏设计（照批 2 UART 先例：`KEY_MATRIX_ROW1_GPIO/_ROW1_PIN`…8 组 16 宏——实施以工单 05 定稿为准）+ 守卫（`i * 4 + j + 1`、0-16 语义、无防抖代码、无 printf）。
- `tests/test_pins.py` STM32_MACRO_VALUES 补（us016/ir_distance 2 宏 + joystick 4 宏 + ec11 6 宏 + key_matrix 16 宏——以实定为 28-30 宏）；test_default_layout.py 白名单按上表。
- 编译矩阵：UV4 0/0（MAIN_C 调全部 API，(void) 化——key_matrix 带 scan 两次、ec11 带 get_delta/read_sw）。
- 词表：us016/ir_distance/joystick 已挂接；**ec11/key_matrix 补录**（B 类——wordlist 感知传感器/输入分类 + models + lib_modules——照批 1 口径）。

## 范围外

- mspm0 条目（前 3 件零改动；B 类无）；vl53l0x（批 4 待资料）；C 类核对（批 11）；上板真机验证（notes——us016 系数/ir 距曲线/EC11 判向/矩阵防抖真机校准留后续）。
- EC11 的 TIM 中断消抖（页面方案）——本件轮询，不占 TIM；EXTI 方案（若用户面板高频旋转需要）范围外（notes 说明可扩展）。
- key_matrix 的连按/释放语义/REPEAT（防抖+键值上报归调用方骨架）；EC11 长按/双击语义（归骨架）。

## 补充说明

- 排序：01 us016 → 02 ir_distance（互替对仗）→ 03 joystick（双通道+SW）→ 04 ec11（B 首个输入类）→ 05 key_matrix（8 脚最重）。
- 页内事实 = %TEMP%\batch7-facts.md（5e56bc0a 报告，2026-09 回填）。
- 收尾清单：全量测试 → sweep 更新 → code-review 两轴 → CONTEXT 补录 → 中文提交。
