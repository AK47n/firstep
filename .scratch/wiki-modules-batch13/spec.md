# 批次 13「收官小批」— 立创 wiki 地猛星手册模块批量入库

## 问题陈述

批次 1-12 共 48 件已入库（遥控/通信、传感器常用、显示/执行、语音/身份、I2C 增强件、环境监测/温度、气体/空气、环境类收尾、ADC 薄封装群、杂项收尾第一/二组、MQ 系收尾、彩屏/显示线）。`lckfb-地猛星移植手册/` 还剩**四篇**库内无对应条目：继电器（control--relay-module）、AS32 LoRa 数传（rf--as32-lora-wireless-communication-module）、BMP180 气压（sensor--bmp180-pressure-sensor）、MS5611 压力/海拔（sensor--ms5611-pressure-sensor）——全部页内自带完整驱动（v7 审计自包含）且**无需网盘**，用户做控制题的执行机构（继电器/断路器）、远距离无线链路（LoRa 双端数传）、气压/海拔检测时 AI 不知道库里有驱动，只能当"需自备"。

本批 = **收官小批**：四件做完即 **70/70 页面全覆盖**（as32 若按决策树砍件则 69/70 + 范围外记录）。

## 方案

照批次 1-12 已确立管线，每件一个工单：手册「代码块」提炼完整驱动（正文内嵌段落禁用）→ 纯驱动切片改造（去 main/printf、API 规范化、ADR 0009 无状态机——AT 指令流程/校准序列归生成骨架）→ 母版 syscfg 新实例（软 I2C=GPIO 2 脚；relay=GPIO 输出 1 脚；as32 按决策树）→ `syscfg_instances.py` INSTANCE_CONSUMERS 登记 → manifest（dependencies、pins、kit+source_url、notes 含手册路径+原页+网盘链接+改造要点+与库内同类分工——气压两件互写、LoRa 与无线件重叠说明）→ wordlist.json 补录（relay=执行机构、as32=无线通信模块、bmp180/ms5611=感知传感器）→ 测试（`tests/test_module_<slug>.py` 照 test_module_joystick.py 模板；test_pins.py::MSPM0_DEFAULT_MAP；test_pin_bindings.py；test_syscfg_prune.py；bmp180/ms5611 压力换算纯函数单测——气压→海拔表，最高既有接缝）→ 编译矩阵（复制 `.scratch/wiki-modules-batch1/run_joystick_matrix.py` 改 slug：单选生成 → SysConfig CLI → gmake 0 error/0 warning 硬门槛）→ verified 回写 → 中文提交 → 工单 resolved → 逐件 code-review（relay 迷你件可浅审）。

## 用户故事

1. 作为做题用户，我选中 `relay` 后，工具自动分配默认脚，生成工程打开即可编译，调用 `relay_init()` + `relay_set(1/0)` 控制继电器吸合/断开（低压控制高压负载）。
2. 作为做题用户，我选中 `as32` 后，生成工程打开即可编译，调用 `as32_send_string/send_hex` 双向透传 + `as32_receive` 轮询收数，做远距离双端遥控/遥测/组网。
3. 作为做题用户，我选中 `bmp180`/`ms5611` 后，调用 init + read 直接出温度/气压（Pa）/海拔，做海拔差检测、无人机定高、气象气压采集。
4. 作为维护者，查看每个新条目能看到平台条目（verified/kit/source_url/网盘链接/改造要点/编译记录/UART 放置决策依据/与库内同类分工），可溯源到手册。

## 实现决策

### 既定事实（勿重新调研）

① ADC12_0 八通道已满（本批无 ADC 件）；② SysConfig 拒绝同外设多 UART 实例（批次 4/10 取证：Resource conflict + 实例上限 4 = UART0-3 外设数）；③ 地猛星 2×20 排针 31 个 IO 全被默认布局占用——默认脚按「同选概率最低」重叠；④ PA0/PA1 不可作 GPIO 输入（2026-09-06 CLI 实证；GPIO 输出可配——ir_remote_tx PA0/gp2y1014au PA1 先例）——软 I2C SDA 需输入，默认脚禁 PA0/PA1；⑤ 母版 GPIO 中断全走 GROUP1 单向量——优先轮询；⑥ 软 I2C 先例 aht10/批次5/sht30/sgp30/ags10（2 GPIO、SDA 运行时切换、delay 依赖、不占硬件 I2C 外设/TIMER）、软 UART TX 先例 jq8900/syn6288、忙等不占 TIMER；⑦ 工具链 `C:/ti/ccs2050`、SysConfig CLI `C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat`；⑧ 页内符号异常/器件正确性缺漏→人工复核、修正并记 notes；⑨ 一致性快检先例 `.scratch/wiki-modules-batch12/sweep_48_modules.py` → 本批后更新 **52 件版**；⑩ **母版 UART 现状（本批取证，2026-09-12 读母版 mspm0.syscfg + syscfg_instances.py 确认）**：UART 实例上限 4 = UART0-3 四个外设，**全部已有实例宿主，无空外设**——UART0 = IMU601 + FINGERPRINT_UART、UART1 = DIGIT_UART + OPENMV4_UART、UART2 = DEBUG_UART + UWB_UART + HC05_UART（3 实例）、UART3 = ZIGBEE_UART（1 实例）；共 8 个 UART 实例定义，生成前按选中模块裁剪、每工程至多 4 实例且每外设至多 1 实例（「裁剪后独占」先例 = fingerprint/open_mv4 单选实证）。

### 共性（四件一致）

- **仅 mspm0 平台条目**（stm32 缺条目 = 生成时 missing 警告，批次 1 先例）；`hardware_bound: false`；`verified` 初始 false，编译矩阵通过转 true；未上板（notes 注明）。
- **代码提炼**：从手册「代码块」章节抽完整 bsp，改造为 `xxx_init()` + 服务函数，去 main/printf，函数名规范化（`Set_Relay_Switch`/`LOAR_`/`BMP180_Get_*`/`MS5611_*`/`Get_TEMP`/`Get_pressure` 库风格重命名），全局状态收敛为模块内静态 + 出参；ADR 0009 无状态机——as32 的 AT 指令流程、bmp180/ms5611 的校准读取序列归**init 封装**（校准数据是每次读数的必需输入，init 缓存为模块静态——sgp30_init 发 0x2003 先例），测量流程控制归生成骨架。
- **软 I2C（bmp180/ms5611）**：照 sht30/sgp30 先例——SCL/SDA 两 GPIO、SDA 方向运行时切换（写=输出、读 ACK/数据=输入）、位操作半周期 5us ≈ 100kHz（页面原值）、延时走 delay 模块、不占硬件 I2C 外设/TIMER；IIC 原语族（start/stop/send_ack/wait_ack/send_byte/read_byte）静态化随模块；**默认脚不得用 PA0/PA1**（既定事实④——SDA 需输入模式）；节点需板上/模块自带上拉。
- **引脚宏参数化**：按 manifest pins 角色 + 母版 syscfg 实例宏名对齐（`<实例>_<引脚>_PIN/IOMUX` 命名，sht30/aht10 先例；UART 走 `<实例>_INST`——fingerprint/open_mv4 先例）。
- **wordlist**：就近分类补录——relay 挂「执行机构」（声光提示器件/执行机构就近，继电器=执行机构）、as32 挂「无线通信模块」（既有「LoRa 数传（SX1278 等）」方案补 lib_modules + models 加 AS32）、bmp180/ms5611 挂「感知传感器」（models + solutions + lib_modules）。
- **默认脚**：按「同选概率最低者与既有默认重叠」分配；**四件默认互不相撞**（PA1 / PA23+PA24 / PA28+PA31 / PA26+PA25）；重叠对写入 `test_pin_bindings` 刻意重叠表。

### 各件决策

| 工单 | slug | 手册 | 外设形态 | 母版 syscfg 实例 | 关键决策 |
|---|---|---|---|---|---|
| 01 | `relay` | control--relay-module.md | GPIO 输出 1 脚（光耦隔离/低电平吸合模块，5V 驱动 250V/10A 高压负载） | 新 GPIO 实例 `RELAY`/OUT（OUTPUT，initialValue **SET = 初始断开**——模块低电平吸合） | **GPIO 迷你驱动（10 分钟级，照 human_ir/microwave_radar 先例）**：API = `relay_init()`（初始断开——调 relay_set(0)）+ `relay_set(uint8_t state)`（**1=吸合（导通）/0=断开——归一化拍板，用户推荐语义**；页面 Set_Relay_Switch 0=吸合/1=断开，本件 relabel：`Set_Relay_Switch(s) ≡ relay_set(1−s)`，manifest notes 写明对照）；**极性单宏 RELAY_ON_LEVEL 承载电平差异**（照 ttp224 TTP224_TOUCH_LEVEL 先例，宏放 .h，默认 **0u** = 引脚低电平吸合——与页面模块「低电平吸合」一致；实物高电平吸合改 1 即可，其余零改动）；页面 RELAY_OUT 宏原式保留为底层（`relay_set` 内 state×RELAY_ON_LEVEL 分发 setPins/clearPins）；无延时依赖（dependencies []）；默认 OUT=**PA1**（与 I2C_0 scl——ml_mpu6050 姿态、GP2Y1014 LED——粉尘重叠：继电器与姿态/粉尘不同框、同选概率最低；PA1 可作 GPIO 输出（既定事实④仅禁输入，ir_remote_tx 先例），板载 4.7k 上拉对推挽输出无碍）；**刻意不叠**声光/执行件（LED_BEEP PA15、电机类、风机控制类）——继电器+蜂鸣报警/电灯控制为常见组合，默认即不撞；同选时经引脚绑定消解 |
| 02 | `as32` | rf--as32-lora-wireless-communication-module.md | **真实 UART 双向（透传数传）**——决策见下节「as32 UART 放置决策」 | 新 UART 实例 `AS32_UART`（peripheral=**UART3**、targetBaudRate=**9600**、enabledInterrupts=[] 轮询、TX=**PA26**/RX=**PA25**——ZIGBEE_UART 原脚） | API = `as32_init()`（清接收状态；页面 LOAR_Init 的 NVIC 使能随轮询裁剪）+ `as32_send_string(const char*)`/`as32_send_hex(const uint8_t*, len)`（页面 LOAR_USART_send_String/HEX 原样：DL_UART_isBusy 忙等 + 逐字节发送）+ `as32_receive(uint8_t *buf, uint16_t max_len)` 返回接收字节数（0=无数据；页面 Anakysis_Data「读到即清」语义：轮询排空 FIFO → 入缓冲（≤max_len−1 截断 + '\0'——**页面 LOAR_RX_LEN 模运算回绕会在满缓冲覆盖首字节，人工复核修正为截断保护，notes 记录**）+ 一次性返回并清缓冲标记）+ `as32_flush()`（页面 Clear_LOAR_RX_BUFF 语义）；缓冲上限保留页面 300（AS32_RX_BUF_MAX）；**AT 配置**：页面**无 AT 指令代码**（「参数的修改是通过上位机进行设置」+ MD0/MD1 硬件模式，页面驱动未接线）→ `as32_init` 不含 AT 封装，AT 指令模板与 MD0/MD1 模式脚 = **范围外**（notes 写明：需要 AT 配置时可经 as32_send 在配置模式下直发——MD 脚由用户接线，或上位机预配置再透传）；dependencies []（轮询无延时） |
| 03 | `bmp180` | sensor--bmp180-pressure-sensor.md | **软 I2C**（SCL 输出 + SDA 双向运行时切换；器件 0xEE 写/0xEF 读） | 新 GPIO 实例 `BMP180`（SCL/SDA 2 associatedPins，均 OUTPUT 初值 CLEARED） | API = `bmp180_init()`（**页面 BMP180_Get_param 序列封装**：0xAA..0xBE 逐项 Read16 读 11 项校准系数入模块静态 struct——AC1..MD，页面原样）+ `bmp180_read(float *temp_c, float *pa)`（页面 Get_Temperature + Get_Pressure 合并：温度 0xF4←0x2E→delay 6ms→读 0xF6 2 字节→X1=(UT−AC6)×AC5/32768.0、X2=MC×2048.0/(X1+MD)、B5=X1+X2 静态、T=((B5+8)/16.0)×0.1；气压 0xF4←(0x34+(oss<<6))（oss=0 页面默认）→delay 10ms→读 0xF6 3 字节→B6..B4/B7/p 全套页面原式；返回 0=成功/1=温度段失败/2=气压段失败——sht20 分段先例，段内细分码（写地址/命令/读地址超时）保留内部）+ `bmp180_read_altitude(float pa)`（**页面原式：44330×(1−pow(p/101325.0, 1/5.255))**——math.h/pow 链接 ir_distance 先例）；页面 GPIO 组名/B5 全局收敛；**人工复核修正（记 notes）**：① 页面 Write_Cmd/Read16 的 NACK printf 改状态码返回（去 printf 后按段返回 1/2/3，页面 Read16 超时 5×1ms 读地址重试保留）；② 页面 `B7` 声明为 uint32_t 使 `B7<0x80000000` 恒真、else 分支不可达——按页面原式保留并与标准 BMP180 实现（long B7 + 真/假分支）标注差异（oss=0 时 `(B7<<1)/B4` 与标准 `(B7*2)/B4` 等价；`B7/B4<<1` 运算符优先级按页面）；③ 页面 Read16 len==3 `>>8` 与 oss=0（`>>(8−oss)`）一致，按页面保留；④ oss 模式参数化不做（固定默认 ultra low power，notes）；⑤ 页面 I2C_WaitAck 先拉高 SCL 再采样（正确——与 jy61p 页面微瑕不同，不需修正）；默认 SCL=**PA23**/SDA=**PA24**——与巡线（HUIDU L2/L3）、无线链路（UWB/HC05/NRF）、色觉（TCS34725）、ADC 槽（us016/mq2 等）重叠：气压/海拔与巡线车控/无线链路/色觉不同框、同选概率最低（刻意不叠温湿度/光照/气体等环境件与显示/语音——气压+环境站/显示为常见搭配；互替件 ms5611 刻意错开），同选时经引脚绑定消解 |
| 04 | `ms5611` | sensor--ms5611-pressure-sensor.md | **软 I2C**（同上；0xEE 写/0xEF 读——CSB 高；PS 上拉 = I2C 模式） | 新 GPIO 实例 `MS5611`（SCL/SDA 2 associatedPins） | API = `ms5611_init()`（页面 main 序列封装：复位 0x1E（0=成功/1=器件地址错误/2=命令无应答——页面码）+ delay_ms(300)（页面「等待初始化完成」）+ Read_PROM 8 字（0xA0..0xAE，C1..C6 = idx1..6，页面原式）+ **页面 PROM 读的 I2C_WaitAck 无应答检查缺漏——人工复核修正：逐段检查应答并返回 3=PROM 读应答失败，notes 记录**）+ `ms5611_read(float *temp_c, float *pressure_pa)`（**页面 2 次转换按原式**：Read_D1_D2(0x48)→delay 10ms→Read_D1_D2(0x58)→delay 10ms→dT=D2−C5×256.0→TEMP=2000+dT×C6/8388608.0→OFF=C2×65536.0+C4×dT/128→SENS=C1×32768.0+C3×dT/256.0→P=(D1×SENS/2097152.0−OFF)/32768.0；温度出参 = **TEMP/100.0（℃）**——页面 Get_TEMP 返回整数℃截断丢小数（dat=(TEMP/1000)*10+(TEMP/100%10)），人工复核修正保留 0.01℃ 分辨率记 notes；气压出参 = **P（Pa）**——P 单位 0.01mbar == 1Pa，页面 /100 = hPa，统一出 Pa 记 notes；返回 0=成功/1=D1 段失败/2=D2 段失败/3=数据读失败——页面 NACK printf 改码，段内细分码保留内部）+ `ms5611_read_altitude(float pa)`（**可选**——同 bmp180 44330 公式，模块共用换算、notes 写分工）；页面 Get_pressure 内部重复调 Get_TEMP()（二次 D1/D2 重读）——本件合并为单次 D1/D2 读取 + 一次 dT/TEMP/OFF/SENS/P 全换算（结果与页面一致，省 ~40ms 总线读），notes 记录；默认 SCL=**PA28**/SDA=**PA31**——低频采集池（IMU601/FINGERPRINT_UART/HX711/SHT30/JY61P/MICROWAVE/TP/OLED_SPI——姿态/称重/身份/温湿度/微波+显示，jy61p「低频采集池」同池先例；MS5611 高精度件与姿态/飞行器定高同框概率最高——池内重叠、同选时经引脚绑定消解；刻意与互替件 bmp180 错开），同选时经引脚绑定消解 |

### as32 UART 放置决策（先取证再动工，本 spec 拍板）

**取证**（读批次 4 spec「UART 资源可行性调研」+ 批次 10/04 结论 + 母版 syscfg/INSTANCE_CONSUMERS 现状，实施时以母版文件为准复核）：
1. SysConfig CLI 实证：同一 UART 外设多实例 = Resource conflict（`UART2 is already in use by ...`）；UART **实例上限 4** = UART0-3 外设数（批次 4 前置调研存档 `.scratch/wiki-modules-batch4/probe/syscfg-master/`）。
2. 母版 UART0-3 **全被实例占用（无空外设）**：UART0=IMU601+FINGERPRINT_UART、UART1=DIGIT_UART+OPENMV4_UART、UART2=DEBUG+UWB+HC05、UART3=ZIGBEE_UART——共 8 个 UART 实例定义，每工程生成前先按选中模块裁剪，裁剪后每外设至多 1 实例、全工程至多 4 实例。
3. 「共享先例」实为**「裁剪后独占」**（批次 1 仅单选实证；批次 4 复证）；FINGERPRINT_UART（UART0/IMU601 宿主）与 OPENMV4_UART（UART1/DIGIT 宿主、与 K230 视觉互替同脚）已按此先例挂靠——新 UART 件照同款模式是库内既定路径（open_mv4 notes 现实约束记录：上限 4——与另 ≤3 件 UART 模块同选在限内、4 件以上 CLI 拒绝）。

**决策树落定（方案①，拍板）**：
- **方案① 真实 UART 独立实例（照 fingerprint/open_mv4「裁剪后独占」先例）——采用**：新增 `AS32_UART`，默认 $assign=**UART3**（宿主 ZIGBEE_UART——LoRa 与 Zigbee 同属无线数传**互替件**、同选概率最低，单选裁剪后独占 UART3；**同选时经引脚绑定换实例/换脚消解**——与 open_mv4×digit_uart 同构）；默认 TX=PA26/RX=PA25（ZIGBEE_UART 原脚——互替件同脚先例：OPENMV4_UART/PA8/PA9 与 DIGIT_UART 同构）；9600（页面「默认波特率 9600」+ AS32 出厂默认）；enabledInterrupts=[] **轮询接收**（无 UART_3_INST_IRQHandler 强符号——zigbee_uart 为 RX 中断件（enabledInterrupts=["RX"]），as32 轮询避免同实例名 ISR 重复；fingerprint/open_mv4 轮询先例）；页面 LOAR_Init/Anakysis_Data/UART_1_INST_IRQHandler 完整保留为驱动实现（IRQHandler 内容改写为轮询排空逻辑——照 open_mv4「IRQHandler 随轮询裁剪」先例）。
- **方案② 软 UART TX（jq8900/syn6288 先例）——不取**：AS32 是**双向数传**（接收为刚需），软 UART 只覆盖发送半程；软 UART RX（GPIO 边沿采样 + 帧解析）库内**无先例**、工作量最大（9600 位时序边沿采样 + 与主循环耦合 + 帧同步），页面 RX 中断直改软采样不可行——评估结论：不可行/不值当。
- **方案③ 砍件 as32——不取**（按用户决策树：① 成立则 ③ 不触发）：① 与既有先例完全同构、零新机制成本；「UART 资源耗尽不可行」的适用前提是"无空外设"——现状确实无空外设，但**占用≠不可用**（8 实例/4 外设现状本身即裁剪后独占的实锤），本件按 open_mv4 同构做法挂靠 UART3 即达成；现实约束与「LoRa 与 NRF24L01（SPI 互替）/HC05（蓝牙）/UWB（定位）/Zigbee（串口数传互替）重叠」随 notes 写明（as32×zigbee 同选 = UART3 双实例 CLI 拒绝——互替件同选概率最低，消解 = 引脚绑定换实例，与 open_mv4×digit_uart 同款；UART 实例上限 4 现实约束同步记录）。
- **最终形态**：真实 UART 双向透传 + 轮询接收；页面语义保留（透传字符串收发、无帧结构——帧/行分帧归调用方骨架，ADR 0009）；AT 配置不落码（页面无 AT 代码，范围外记录）。

### 默认脚与重叠全景（定稿，test_pin_bindings 刻意重叠表登记）

| slug | 默认脚 | 重叠主体（同选概率最低） |
|---|---|---|
| `relay` | OUT=PA1 | I2C_0 scl（ml_mpu6050 姿态）+ GP2Y1014 LED（gp2y1014au 粉尘）——继电器与姿态/粉尘不同框（**刻意不叠**声光/执行件：LED_BEEP PA15、电机类、风机——继电器+报警/电灯控制为常见组合） |
| `bmp180` | SCL=PA23 / SDA=PA24 | HUIDU L2/L3（巡线）+ UWB/HC05 链路 + NRF24L01 CSN/MOSI + TCS34725 SCL/SDA + ADC12_0 adcPin3——气压/海拔与巡线车控/无线链路/色觉不同框（**刻意不叠**温湿度/光照/气体等环境件、显示/语音——气压+环境站/显示为常见搭配；与互替件 ms5611 错开） |
| `ms5611` | SCL=PA28 / SDA=PA31 | IMU601/FINGERPRINT_UART/HX711/SHT30/JY61P/MICROWAVE/TP_XPT2046/OLED_SPI（低频采集池——姿态/称重/身份/温湿度/微波/显示；MS5611 高精度件与姿态/定高同框概率最高，jy61p 同池先例；与互替件 bmp180 错开） |
| `as32` | TX=PA26 / RX=PA25 | ZIGBEE_UART（**UART3 同外设**——LoRa 与 Zigbee 无线数传互替）+ HUIDU R2/L4 + NRF24L01 CLK/MOSI + TTP224 OUT2/3 + IR_REMOTE + ADC12_0 adcPin1/2 |

- **四件默认互不相撞**（PA1 + PA23/PA24 + PA28/PA31 + PA26/PA25）——执行机构+无线链路+双气压互替件罕有全同框；两两组合（继电器+低压传感、LoRa 遥控+继电器、气压+无线遥测）默认即不撞。
- 与既有默认重叠计数更新（test_pin_bindings.py 刻意重叠表）：**PA1 2→3**（relay）、**PA23 6→7 / PA24 6→7**（bmp180）、**PA28 7→8 / PA31 7→8**（ms5611）、**PA25 5→6 / PA26 6→7**（as32）、**UART3 新增 =1**（ZIGBEE_UART + AS32_UART——外设级重复登记，open_mv4 UART1 先例）。

### 网盘依赖（本批无）

本批四件页内源码完整（v7 审计 58 篇自洽名单内；实施时复跑 `.scratch/wiki-materials/audit_v7.py` 确认）。例外项随 notes 记录、不阻塞：全部未上板（继电器吸合/断开时序、LoRa 透传距离、软 I2C 时序 + 补偿公式真机验证留后续）。

## 测试决策

照批次 1-12 先例逐件：

- `tests/test_pins.py`：`MSPM0_DEFAULT_MAP` 增 7 行——relay `("RELAY","OUT")`、bmp180 `("BMP180","SCL"/"SDA")`、ms5611 `("MS5611","SCL"/"SDA")`（GPIO 组 $name）、as32 `("AS32_UART","txPin"/"rxPin")`；无引脚字面量新增豁免（四件全走 syscfg 生成宏；as32 用 `AS32_UART_INST`，不得出现 `UART_3` 字面量）。
- `tests/test_pin_bindings.py` 刻意重叠表更新（上表 7 行 + UART3 外设行，注释按既有文体写明理由与批次号）。
- `tests/test_syscfg_prune.py` 增 RELAY/BMP180/MS5611/AS32_UART 实例保留（单选各自）/裁剪（hc05 单选）断言。
- 新增 `tests/test_module_relay.py` / `test_module_as32.py` / `test_module_bmp180.py` / `test_module_ms5611.py`（照 test_module_joystick.py 模板）：manifest 结构（仅 mspm0 + 依赖 + 角色默认 + notes 关键子串）+ mspm0 单选生成（syscfg 含实例、模块文件落盘、main.c 调 init/服务函数过静态门禁）+ 关键守卫：
  - relay：`RELAY_ON_LEVEL 0u` 极性宏 + `relay_set(1)=吸合`（RELAY_ON_LEVEL=0u 分支 → clearPins）/`relay_set(0)=断开`（setPins）+ init 初始断开（setPins）+ 页面 `Set_Relay_Switch(s) ≡ relay_set(1−s)` 对照注释 + 无 printf/IRQHandler/main；
  - bmp180：`345478186`? 否——守卫 = 寄存器地址 `0xAA`/`0xBE`/`0xF4`/`0xF6`/`0x2E`/`0x34`、器件地址 `0xEE`/`0xEF`、系数 `32768.0`/`2048.0`/`0.1f`、海拔 `44330`/`101325.0`/`5.255`、`& 0xFFFC` 不出现（BMP180 无掩码）、无 printf；**压力换算纯函数单测（最高既有接缝）**——Python 镜像 `bmp180_altitude(pa)`（44330 公式），断言气压→海拔表（101325→0.0m、100000→~90m、95000→~551m? 实施时用 math.pow 计算基线表并断言 ±0.5m）;
  - ms5611：`0x1E` 复位、`0xA0` PROM 基址、`0x48`/`0x58` 转换命令、`0xEE`/`0xEF`、系数 `256.0`/`8388608.0`/`65536.0`/`32768.0`/`2097152.0`、温度 `TEMP/100.0`、气压出 Pa（0.01mbar）、`10`ms 转换等待、无 printf；同理压力换算纯函数表（共用 altitude 公式镜像——两件共用同公式、各自断言）；
  - as32：`9600`、`AS32_UART_INST`、`isRXFIFOEmpty` 轮询、无 `IRQHandler`/`NVIC`、`AS32_RX_BUF_MAX 300`、发送 `DL_UART_isBusy` + `transmitData`、receive 清缓冲语义 + 截断保护、manifest notes 子串（「UART3」「实例上限」「zigbee」「页面无 AT」）。
- **wordlist 预算**：四件入库后按批次 12 口径实测默认词表 wire 字节（现有 wire 7239 / WORDLIST_PROMPT_BYTES 7500 / fit 上限 7500−166=7334，余量 95B——本批预计 +300~400B 超限）：超限则上调 WORDLIST_PROMPT_BYTES（预计 7900，实测后定）并同步 llm.py/budget.py 记账链（批次 5/7/8/9/12 先例），test_wordlist_segment 契约不截断、结构测试绿。
- 编译级验收：复制 `run_joystick_matrix.py` 改 slug（.scratch/wiki-modules-batch13/run_<slug>_matrix.py ×4，MAIN_C 调 init + 服务函数；**as32 单选含 UART3 实例 → PA26/PA25 过 SysConfig CLI；bmp180/ms5611 单选含软 I2C GPIO 实例 + pow 链接（math）过 gmake**；relay 单选含 RELAY OUT 实例），gmake 真编译（`C:/ti/ccs2050`）0 error 硬门槛、模块自身 warning 0；结果回写 manifest verified/notes。

## 范围外

- stm32 平台条目（仅 mspm0，批次 1 先例）、上板真机验证（未上板，notes 注明——继电器吸合时序/低电平驱动、LoRa 距离与波特率、软 I2C 时序与温度补偿真机验证留后续）。
- as32：AT 指令模板（AS32-TTL 标准 AT 命令——页面无代码，参数经上位机设置）+ MD0/MD1 模式脚 GPIO 驱动（页面驱动未接线，透传模式 M0=M1=0 默认）——如需 AT 配置经 as32_send 在配置模式直发或上位机预配置（notes 写明）；页面帧格式（透传无帧结构——行分帧/校验归调用方骨架）。
- bmp180：oss 工作模式参数化（固定 oss=0 ultra low power ultra low 默认——页面默认）、BMP280/BME280 换代（BMP180 已停产老器件——库内无 BMP280/BME280 条目，另议）。
- ms5611：OSR 参数化（固定 4096——页面）、SPI 模式（PS 拉低——本件 I2C 模式）。
- 正文内嵌段落（行拆散版）不作为提炼源。
- 若实施中出现「① 被否 → 砍件 as32」路径（用户改判）：本 spec 记录范围外「LoRa 与 NRF/BLE/zigbee 重叠、UART 资源耗尽不可行」→ 70/70 改为 69/70 收官（收官定义按用户口径）。

## 补充说明

- 排序：01 relay（10 分钟级迷你打样）→ 02 as32（UART 决策取证先行）→ 03 bmp180 → 04 ms5611；四件互相独立可并行（as32 的 UART 取证 = 本 spec 已拍板，工单可直接开做）。
- 词表预算链：见测试决策——实施实测后按先例上调并记 spec。
- 收官定义（本批完成即达成）：**70/70 页面全覆盖**（或 as32 砍件则 69/70 + 范围外记录）→ **全量测试**（pytest + node:test 全绿）→ **一致性快检 52 件版**（`.scratch/wiki-modules-batch13/sweep_52_modules.py`——照 sweep_48_modules.py 更新）→ **批次 1-13 全部 code-review 收尾**（relay 浅审、as32/bmp180/ms5611 深审 + 48 旧件对仗核对）→ **CONTEXT.md 平台行补录批次 13 块 + README 终稿核对**（模块数/覆盖说明）→ **中文提交**（.githooks/commit-msg 强制中文；新增 .ps1 必须 UTF-8 with BOM）。
- 审计脚本 `.scratch/wiki-materials/audit_v7.py` 可复跑；本批四件均在 v7 全自洽清单（70−12 真·页外符号）内。
- 工单：`issues/01-module-relay.md` → 02 as32 → 03 bmp180 → 04 ms5611。
