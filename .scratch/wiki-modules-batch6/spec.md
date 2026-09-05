# 批次 6「环境监测/温度补充第一组」— 立创 wiki 地猛星手册模块批量入库

## 问题陈述

批次 1「遥控/通信」（joystick/hc05/nrf24l01/ir_remote）、批次 2「传感器常用」（dht11/us016/bh1750/ir_distance）、批次 3「显示/执行」（max7219/pca9685/ir_remote_tx）、批次 4「语音/身份」（jq8900/syn6288/rc522/fingerprint）、批次 5「I2C 增强件」（ads1115/tcs34725/mlx90614/at24c02）共 19 件已入库。`lckfb-地猛星移植手册/` 剩余页中**环境监测/温度补充第一组**四篇页内自带完整驱动源码（v7 审计自包含，2026-09-07 复跑确认 12 篇真缺页外符号名单中无本批四件）：DS18B20 单总线温度（学生常见件）、SHT30 软 I2C 温湿度、MQ-2 烟雾（ADC 模拟量）、TTP224 4 路电容触摸——模块库仍无对应条目：用户做环境监测/温控/气体检测题时，AI 不知道库里有驱动，只能当"需自备"。

按用户裁决：批次 6 = **环境监测/温度补充第一组**四件——全部页内源码完整（v7 全自洽）、无需网盘。

## 方案

照批次 1-5 已确立管线，每件一个工单：手册「代码块」提炼完整 bsp（正文内嵌段落禁用）→ 纯驱动切片改造（去 main/printf、API 规范化、ADR 0009 无状态机）→ 母版 syscfg 新 GPIO 实例 / ADC12_0 消费登记（薄封装不新开实例）+ `syscfg_instances.py` INSTANCE_CONSUMERS 登记 → manifest（dependencies/pins/kit+source_url/notes 含手册路径+原页+网盘链接+改造要点+与库内同类分工）→ wordlist.json 补录（感知传感器，lib_modules 挂接）→ 测试（`test_module_<slug>.py` 照 test_module_joystick.py 模板 + test_pins.py / test_pin_bindings.py / test_syscfg_prune.py 增断言）→ 编译矩阵（复制 run_*_matrix.py 改 slug：单选生成 → SysConfig CLI → gmake 0 error/0 warning 硬门槛）→ verified=true 回写 → 中文提交 → 逐件 code-review。

## 用户故事

1. 作为做题用户，我选中 `ds18b20`/`sht30`/`mq2`/`ttp224` 后，工具自动分配默认脚，生成工程打开即可编译，可调用 init + 服务函数。
2. 作为做题用户，我做高精度温度测量（DS18B20 单总线）、环境温湿度（SHT30 软 I2C）、可燃气体/烟雾检测（MQ-2 模拟量）、触摸按键面板（TTP224 4 路）时，不用再读器件手册、不用自写时序。
3. 作为维护者，查看每个新条目能看到平台条目（verified/kit/source_url/网盘链接/改造要点/编译记录/与库内 aht10/dht11 等分工），可溯源到手册。

## 实现决策

### 既定事实（勿重新调研，批次 1-5 已实证）

① 母版 `ADC12_0` 已是 sequence 四通道（endAdd=3：MEM0=adc+us016 薄封装共读 / MEM1-2=joystick / MEM3=ir_distance）——mq2 走**薄封装**共读 MEM0，不新增通道（新开需 endAdd+1 并同步 joystick/ir_distance 测试断言与 test_pin_bindings 表，本批不采用）；② SysConfig 拒绝同一 UART 外设多实例——本批无 UART 件；③ 地猛星 2×20 排针 31 个 IO 全被默认布局占用——新模块默认脚按「同选概率最低者与既有默认重叠」，同选经引脚绑定消解；④ 母版 GPIO 中断全走 GROUP1 一个向量且被 KEY/motor 编码器消费——本批全部轮询，不注册中断；⑤ 软 I2C 先例 aht10/批次 5 四件（默认脚已占 PB6/PB7、PA16/PA17、PA23/PA24、PA9/PA8、PB24/PB8——本批新软 I2C 再挑「同选概率最低」脚且尽量不与批次 5 相撞）、软 SPI 先例 nrf24l01/max7219/rc522、软 UART TX 先例 jq8900/syn6288、忙等不占 TIMER（TIMG0/6/7/8/12 全占）；⑥ 工具链 `C:/ti/ccs2050`、SysConfig CLI `C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat`；⑦ 页内符号异常人工复核（上游缺陷剔除并记 notes）。

### 共性（四件一致）

- **仅 mspm0 平台条目**（stm32 缺条目 = 生成时 missing 警告，批次 1 先例）；`hardware_bound: false`；`verified` 初始 false，编译矩阵通过转 true；未上板（notes 注明）。
- **代码提炼**：从手册「代码块」章节抽完整 bsp，改造为 `xxx_init()` + 服务函数，去 main/printf，函数名规范化（去 `DS18B20_GetTemperture`/`Key_IN1_Scanf`/`SHT30_Read` 菜市场命名按库风格重命名），全局状态收敛为模块内静态 + 出参指针（sht30 页外 `extern double Temperature, Humidity` 全局收敛为出参）。
- **时序**：微秒/毫秒延时全走库内 `delay` 模块（`dependencies: ["delay"]`）；**不占 TIMER**（TIMG0/6/7/8/12 已被全占，dht11/ir_remote_tx 先例）；**不注册 GPIO 中断**。
- **ADC 轮询**：页面 `ADC12_0_INST_IRQHandler` + `gCheckADC` 标志位按 joystick 先例改依赖 adc 模块轮询读（共享实例 IRQHandler 强符号唯一）。
- **引脚宏参数化**：按 manifest pins 角色 + 母版 syscfg 实例宏名对齐（`<实例>_<引脚名>_PIN`/`_IOMUX`，SysConfig 命名 `<实例>_<引脚名>_IOMUX`，aht10 编译矩阵实测；跨端口多脚实例无合并 PORT 宏，按引脚名分派 `<实例>_<引脚名>_PORT/PIN`，max7219 先例）。
- **默认脚**：按「同选概率最低者与既有默认重叠」分配；本批四件（含 ADC 薄封装 mq2 的 MEM0 槽位）默认**互不相撞**；重叠对写入 `test_pin_bindings` 刻意重叠表。
- **wordlist**：感知传感器组补录四件（名称 + `lib_modules` 挂接），models 加词条。

### 各件决策

| slug | 手册 | 外设形态 | 母版 syscfg 实例 | 关键决策 |
|---|---|---|---|---|
| `ds18b20` | sensor--ds18b20-temp-sensor.md | 1-Wire 单总线温度（1 GPIO 双向，方向运行时切换） | 新 GPIO 实例 `DS18B20`/DATA（OUTPUT、initialValue SET=空闲高，运行时 DQ_OUT/IN 切换——DHT11 先例） | API = `ds18b20_init`（复位检测器件，返回 0=检测到 1=未检测到，页面 DS18B20_Init/Check 语义）+ `ds18b20_read_temp`（出 float ℃——页面 GetTemperture 语义：0xCC+0x44 转换 → 0xCC+0xBE 读 2 字节 → dataH&0x80 负温补码 `(~temp)+1` × **-0.0625** / 正温 × **0.0625**，±0.5℃ 精度、12bit 默认分辨率 0.0625 系数按页面）；位时序按页面原样：复位低 750us+释放 15us+应答等待 200×1us+释放等待 240×1us；写位 1 = 低 2us+高 60us、写位 0 = 低 60us+高 2us；读位 = 低 2us+释放+输入 12us 采样+50us 尾部（位槽 62-64us，页面 60-70us 区间）；`dependencies: ["delay"]` 忙等不占 TIMER；**上游缺陷记录**：页面头文件声明 `DS18B20_Reset(void)` 但 .c 无定义 → 剔除该声明（notes）；页面正文仅读 2 字节温度（未读第 9 字节 CRC），本实现按页面不加 CRC 校验（notes）；默认 DATA=PA7——与 DC_MOTOR BIN2（双电机）、SERVO_PWM ccp0（舵机）、RC522 CS（读卡）重叠：接触测温与运动控制/读卡不同框、同选概率最低（刻意不叠温湿度/光照/显示/语音件——测温+显示/语音/传感站为常见搭配，同 mlx90614 选型口诀；不叠 I2C_0 的 PA0/PA1——硬件 I2C 脚与 i2c_bus_share 测试互扰，批次 5 实测调整先例），不与批次 5/同批默认相撞 |
| `sht30` | sensor--sht30-temp-humi-sensor.md | 软 I2C 温湿度（2 GPIO，SDA 方向运行时切换） | 新 GPIO 实例 `SHT30`/SCL+SDA（照 AHT10 先例，不占硬件 I2C 外设） | API = `sht30_init`（写周期模式命令 0x2130——页面 SHT31_Write_mode 语义）+ `sht30_read(&t,&h)`（完整读：周期读命令 0xE000 → 重发读地址应答重试 ≤20×2ms → 6 字节（温高/低/CRC + 湿高/低/CRC）→ **CRC8 校验保留**（页面原式 POLYNOMIAL 0x31、初值 0xFF，两组各校验 2 字节）→ 换算按页面 0.01 系数：`t=(d/65535.0)*175.0-45`、`h=(d/65535.0)*100.0`）+ `sht30_read_temperature(&t)` / `sht30_read_humidity(&h)`（出参便捷封装，内部完成一次 read）；失败返回 1-5（0=成功；1/2/3 = 命令/地址应答失败、4 = 读地址应答超时、5 = CRC 校验失败——页面失败码）；页面规格温度 ±0.3℃/湿度 ±2%RH，SHT30 数据手册典型 ±0.2℃/±2%RH（指令「±0.2℃」按典型值，notes 注明）；**上游缺陷记录**：字节计数/延时按页面原式；SHT31_Write_mode 页面把 `IIC_Stop()` 注释掉（重复起始），按页面原样不补 STOP（notes）；默认 SCL=PA28/SDA=PA31——与 IMU601 UART0（+FINGERPRINT_UART）、HX711 SCK/DT 重叠：温湿度与姿态/称重/身份采集不同框、同选概率最低；刻意不叠 PB6/PB7（aht10 温湿度互替）与批次 5 八脚；同选时经引脚绑定消解 |
| `mq2` | sensor--mq-2-sensor.md | ADC 模拟量薄封装（电压 → 百分比） | **无新实例**——依赖 adc 模块共享 ADC12_0 MEM0 槽位（us016 先例） | `dependencies: ["adc"]`；API = `mq2_init`（adc_init 转 ADCMEM0）+ `mq2_read_percent`（adc_get(ADC_1, ADC_Channel_0) → `(float)adc_new/4095.0f*100.0f` 出 0-100%；页面 Get_Adc_Value 30 次平均改 5 次快速平均——us016 快平均先例；页面 ADC 中断（IRQHandler + gCheckADC）改依赖 adc 模块轮询（共享实例 IRQHandler 强符号唯一）；页面 `GET_DO` 宏未使用 → 不声明 DO 角色（阈值由模块可调电阻控制，notes 说明）；**notes 写明 MQ 系读数是相对值非 ppm 精标**（需预热、标准气体标定才能映射 ppm）；默认脚 = MEM0 槽位 PA24（无新 $assign 行；与批次 5 tcs34725 SDA 重叠系槽位唯一所致，同选经引脚绑定消解——tcs34725 SDA 换脚即可）；角色 id `MQ2_AO_CH0`（尾 `_CH<N>` 推导 MEM 索引，us016 先例） |
| `ttp224` | sensor--ttp224-touch-sensor.md | 4 路电容触摸按键（4 × GPIO 输入，上拉） | 新 GPIO 实例 `TTP224`/OUT1-4（INPUT + internalResistor PULL_UP——页面「上拉输入」） | API = `ttp224_init`（GPIO 由 SYSCFG_DL_init() 生效，空实现占位保持 API 一致——joystick/sw 先例）+ `ttp224_read(ch)`（ch 1-4 按页面 Key_IN1-4 序，返回 1=触摸 0=未触摸，越界返回 0）+ `ttp224_read_all()`（位掩码低 4 位：bit0=通道1 … bit3=通道4，1=触摸）；**极性按页面原样：引脚高 = 触摸（页面 TTP223B 正文描述与页面代码 `KEY_INx` 宏同口径——read 直接返回引脚电平；用户裁决「按页面资料」；notes 记录 TTP224N 实际常为低有效、如需反相改一处宏 `TTP224_TOUCH_LEVEL` 即可）；页面 4 个 `Key_INx_Scanf` 收敛为 `read(ch)/read_all`；默认 OUT1=PA22/OUT2=PA25/OUT3=PA26/OUT4=PA27——与 HUIDU L1/L4/R1/R2（巡线）+ DEBUG_UART RX/NRF IRQ + ZIGBEE/joystick/IR_REMOTE/ADC MEM3（ir_distance）重叠：触摸按键与无线链路/手动输入互替、与巡线/测距不同框，同选概率最低；四脚与同批默认（PA7/PA28/PA31/PA24）不撞 |

### 默认脚与重叠全景（2026-09-07 定稿）

四件默认 = **PA7（ds18b20）、PA28/PA31（sht30）、PA24（mq2，MEM0 槽位无新 $assign 行）、PA22/PA25/PA26/PA27（ttp224）**——全部与既有默认重叠（同选概率最低者）、四件互不相撞（环境监测站 = 温度+气体+触摸面板最常见组合，默认即不撞）。

- 与既有默认重叠计数（更新 test_pin_bindings.py 刻意重叠表）：PA7 3→4、PA22 3→4、PA25 4→5、PA26 5→6、PA27 2→3、PA28 3→4、PA31 3→4；PA24 计数不变（仍 6——mq2 薄封装共享 MEM0 同一条 $assign 行，无新行），注释补 mq2。
- 与批次 5 八脚（PA16/PA17/PA23/PA24/PA9/PA8/PB24/PB8）相撞情况：仅 mq2 的 PA24 不可避免（ADC12_0 MEM0 槽位唯一——tcs34725 SDA 同脚，同选经引脚绑定消解）；sht30（PA28/PA31）、ds18b20（PA7）、ttp224（PA22/25/26/27）均不与批次 5 相撞。
- 软 I2C × 硬件 I2C 同脚（PA0/PA1 = I2C_0 外设脚）物理冲突分组：本批 ds18b20 刻意**不叠** PA0/PA1（单总线 GPIO 虽不受 i2c_bus_share 分组约束，但会与既有 i2c_bus_share 测试互扰——批次 5 实测调整先例）。

### 网盘依赖（本批无）

本批四件页内源码完整（v7 审计通过）。例外项随 notes 记录、不阻塞：全部未上板（单总线位时序/软 I2C 时序/ADC 换算/触摸极性真机验证留后续）。

## 测试决策

照批次 1-5 先例逐件：

- `tests/test_pins.py::MSPM0_DEFAULT_MAP` 增映射 7 条（ds18b20 DATA、sht30 SCL/SDA、ttp224 OUT1-4；mq2 的 adc 角色无 GPIO 组/外设字段落点，由 test_pin_bindings 落点唯一性覆盖——us016 先例）；
- `tests/test_pin_bindings.py` 刻意重叠表更新（PA7/PA22/PA25/PA26/PA27/PA28/PA31 计数与注释；PA24 注释补 mq2 共读）；
- `tests/test_syscfg_prune.py` 增 DS18B20/SHT30/TTP224 实例与 ADC12_0 新消费方（mq2）保留/裁剪断言；
- 新增 `tests/test_module_ds18b20.py` / `test_module_sht30.py` / `test_module_mq2.py` / `test_module_ttp224.py`：manifest 结构（仅 mspm0 + 依赖）+ mspm0 单选生成（syscfg 含实例 + 模块文件落盘 + main.c 调 init/服务函数过静态门禁）；
- **关键源码守卫**（防公式/时序走样，ir_remote_tx `burst_cycle_formula_guard` / ads1115 公式守卫先例）：
  - ds18b20：位槽时间轴常量守卫（读位采样点 12us、读位尾部 50us、写位 60us、复位 750us——12us/60us 位槽时间轴钉死，总槽 62-64us 落在页面 60-70us 区间；源码仅引用常量不散写字面量）、负温 `-0.0625` 系数守卫、去除 `DS18B20_Reset` 声明守卫（页面头声明无定义）；
  - sht30：CRC8 原式守卫（`0x31`/`0xFF`）、换算公式守卫（`* 175.0f - 45.0f`/`* 100.0f`）、命令常量守卫（`0x2130`/`0xE000`/`0x44`）；
  - mq2：百分比公式守卫（`4095`/`100.0f`、`ADC_Channel_0`）、无 IRQHandler 守卫（轮询，`ADC12_0_INST_IRQHandler` 不得出现）；
  - ttp224：页面极性守卫（`TTP224_TOUCH_LEVEL` 宏单点反相、read 返回 1=触摸）、4 通道位掩码守卫（`read_all` bit0-3）。
- 编译级验收：复制 `run_joystick_matrix.py` 改 slug（四件各一），gmake 真编译（`C:/ti/ccs2050`）0 error 硬门槛、模块自身 warning 0；结果回写 manifest verified/notes。

## 范围外

- stm32 平台条目、上板真机验证（真机留后续，notes 注明）、新 ADC/TIMER/硬件 I2C 外设实例（mq2 薄封装、其余 GPIO 实例，本批不开 ADC 新通道）。
- 正文内嵌段落（行拆散版）不作为提炼源。
- DS18B20 多器件 ROM 寻址（0x55 匹配/0xF0 搜索）、报警寄存器（0x4E/0x48）、第 9 字节 CRC 读取、寄生供电——页面未实现，不实现（notes 说明）。
- SHT30 单次测量模式（0x2C06/0x2400）、时钟拉伸、软复位命令（0x30）、周期测量节拍切换（0x2024 等）——页面仅周期模式通路，不实现（notes 说明）。
- MQ-2 DO 数字量阈值读取（页面仅 `GET_DO` 宏未使用；阈值由模块可调电阻控制）、ppm 级精确标定（MQ 系为相对值，需标准气体标定）。
- TTP224 低功耗模式检测/12 秒节拍（页面仅描述未实现）、4 键多点同时触摸去抖（页面按电平直读）。
- 批次 7a 气体群（MQ-3/4/5/6/7/8/9、mq-135、ms1100、ags10、sgp30）、7b ADC 模拟量薄封装群、7c GPIO 薄封装群、7d 杂项、8 彩屏线（需网盘）另立工单。

## 补充说明

- 审计脚本 `.scratch/wiki-materials/audit_v7.py` 2026-09-07 复跑：真缺 12 篇（nrf24l01、8 篇彩屏、mpu6050 等）——本批四件均在全自洽 58 篇内。
- 工单：`issues/01-module-ds18b20.md` → 02 sht30 → 03 mq2 → 04 ttp224（互相独立，可并行；实施按简→繁：ds18b20（单总线先例最全）→ sht30（软 I2C 先例）→ mq2（薄封装最简）→ ttp224（4 输入薄封装））。
- 完成后：全量测试套件 + 批次 1-6 全部 23 件 code-review 收尾 + CONTEXT.md 平台行补录 + 中文提交（.githooks/commit-msg 强制中文；.ps1 若新增按 UTF-8 with BOM 存）。
