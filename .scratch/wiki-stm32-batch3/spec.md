# 批次 3「软 I2C 器件库组 + HX711 称重」— 立创 wiki 地阔星 STM32F103C8T6 手册模块批量入库（stm32 线）

## 问题陈述

stm32 线进度：批次 1（GPIO 迷你件 6 件）+ 批次 2（软 I2C 总线件 6 件）已入库（12 件，矩阵 0/0，pytest 3614 全绿）。剩余 mspm0 单平台件中下一组 = **器件库类软 I2C 件**（外扩 ADC/色觉/测温/气体/舵机驱动——页面驱动 4-6 块、含寄存器/命令表/CRC/换算，比批次 2 总线件更大）+ **HX711 称重**（GPIO 双线，非 I2C——同批打磨双形态）。

**批次 2 前置缺陷（本批回修）**：实测 aht10_stm32.c 的 **SCL 从未 `gpio_init` 为输出**（init L124-138 只做总线序列，SCL 只有 `gpio_set`；全库 grep OUT_OD 仅 SDA 命中）——F1 复位后 GPIO 为浮空输入，ODR 写入无效 → SCL 无法驱动总线（编译绿、未上板未暴露，真机必死）。批次 2 六件同构（同一模板），本批先开**回修工单 01**（六件补 SCL OUT_OD 初始化+置高 + 矩阵复跑 + 防回潮守卫），本批 5 件 I2C 全部按正确样式实现。

## 方案

照批次 1/2 管线：批次 2 已实证的软 I2C 模式直接沿用——**模块内静态 `_iic_*` 原语族（不用母版 ml_i2c）**、**逐脚端口宏 `<SLUG>_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN`（4 宏/件）**、**默认共总线 PA6/PA7**（与 motor 方向脚重叠 = 同选概率最低）；HX711 按 GPIO 双线件（`<SLUG>_SCK/DT_*` 4 宏）。每件：手册「代码块」提炼 → 纯驱动切片（去 main/printf、API 与 mspm0 全对齐、页面缺陷人工复核修正+notes+守卫）→ 换算 ml_* → pin_config.h 宏段（**I2C 件 init 必须 SCL OUT_OD 初始化+置高**）→ manifest stm32 条目 → 测试 → UV4 矩阵 0/0 → verified → 中文提交。

## 用户故事

1. 作为做题用户，选 stm32 + ads1115/tcs34725/mlx90614/sgp30/pca9685 后，`<slug>_init()` + 服务函数（出参带回/双出参/16 路 PWM/角度）直接可用，不再「需自备」。
2. 作为做题用户，选 stm32 + hx711 后，`hx711_tare/read_raw/get_gram` 直接称重（24bit 补码、超时保护、去皮），不再「需自备」。
3. 作为做题用户，同时选多个总线件：本批 5 件与批次 2 六件**共挂同一总线 PA6/PA7**（地址全异——除 pca9685 0x40 × sht20 0x40（见地址冲突裁决）；同址对经 `pca9685_set_address` 或绑定换线）。
4. 作为维护者，看得到每件 stm32 条目（verified/kit/source_url=wiki 原页/notes 含手册路径+网盘+页面缺陷修正记录+SCL 初始化修正说明），可溯源。

## 实现决策

### 既定事实（勿重新调研；批次 2 实证 + 本批页面事实已取证 batch3-facts.md）

① **软 I2C 模式（批次 2 拍板直接沿用）**：模块内静态 `_iic_*` 原语族（start/stop/send_ack/wait_ack/send_byte/read_byte），SDA_OUT//IU 方向切换（gpio_init 重配，页面原式 OD/IPU），SCL=SDA 电平 `gpio_set`，SDA_GET=`gpio_get`，时序常量 = 页面原值（半周期 2-5us），延时走 delay 模块（依赖 ["delay"]），**零 ml_i2c 调用、零寄存器级/标准库调用**。

② **回修口径（本批新增大前提）**：**I2C 件 init 必含 `gpio_init(<SLUG>_SCL_GPIO, <SLUG>_SCL_PIN, OUT_OD)` + SCL 置高**（F1 复位浮空，不初始化 = 总线死）；批次 2 六件按工单 01 回修；**测试守卫**：每个 I2C 件 test 断言 init 文本含 SCL OUT_OD 初始化（防回潮）。

③ **引脚宏与默认脚**：I2C 5 件 = 逐脚 4 宏 + 默认 SCL=PA6/SDA=PA7（共总线——与批次 2 六件同总线、地址全异合法共享；重叠 MOTOR_A_DIR/DIR2，同选概率最低推理同批次 2）；HX711 = `HX711_SCK_GPIO/PIN`+`HX711_DT_GPIO/PIN` 4 宏，默认 **SCK=PB5 / DT=PB0**（推理：称重/电子秤与「光电编码器闭环小车」（PB5=MOTOR_A_ENC）与「单电机方向」（PB0=MOTOR_B_DIR）不同框；**刻意不叠**本批 I2C 件与常见传感站件（flame/ir_beam/human_ir 等采集类——称重+传感站同框概率高）、声光件）；页面默认全不照抄（互抢既有占用：PB8/9=OLED、PA0/1=ADC/PWM、PA5/6=flame/总线）。

④ **页面事实（6 页全 F1 标准库，无 F4）**（详细行号证据见 %TEMP%\batch3-facts.md）：
| 件 | 地址/协议 | 页面缺陷要点 | mspm0 API（对齐签名） |
|---|---|---|---|
| ads1115 | 0x48（0x90/0x91），16bit 补码，config 0xC283 | ① **负值换算错误**：`(65535-num)*0.000125` 近似 + `>32768` 未含 32768——改 int16_t 直乘 0.000125；② 失败返 -1.0 与合法 -1.0V 混用（但 mspm0 API 已出参+状态码化）→ 照 mspm0；③ 注释 3/4 返回码未实现；④ printf 残留；⑤ delay_1ms(1) 库内无；⑥ 页面默认 PB8/PB9 | `init/write_register/write_config/read(ch)→int16_t/read_voltage(ch)→float/set_gain/set_data_rate` |
| tcs34725 | 0x29（0x52/0x53+CMD_BIT 0x80），RGBC 低字节前 | ① 读写路径 NACK 全丢；② RGBtoHSL c==0 除零；③ extern rgb/hsl 泄漏；④ `id==0x4D \| id==0x44` 按位或→`\|\|`；⑤ TC34725 拼写；⑥ 页面默认 SDA=PB8/SCL=PB9 | `init/read_rgb(RGBC*)/rgb_to_hsl/ set_integration_time/set_gain/enable/disable` |
| mlx90614 | 0x5A，0.02K/LSB−273.15 | ① **PEC/CRC 禁用**（定义未调用、读时序无 PEC 字节——按 mspm0 先例剔除+notes）；② 失败 return 0.0 与合法 0℃ 混用→出参+状态码；③ 注释 MLX90615 笔误；④ 「必须开漏」注释 vs 代码 Out_PP——**按总线协议与批次 2 先例统一 OUT_OD**（页面代码差异记 notes）；⑤ 写-读间 delay_ms(1) 被注释掉→**加回**（时序点）；⑥ 无温补/发射率修正（mspm0 同，notes） | `init()/read_object_temp(float*)/read_ambient_temp(float*)` |
| sgp30 | 0x58，0x2003/0x2008，CO2/TVOC 双出参 | ① **CRC 缺失**：`crc=crc` 自赋值丢弃 + 只读 5 字节漏 TVOC CRC → 读满 6 字节 + 两组 CRC8（0x31/0xFF）；② NACK 全丢；③ 正文地址位语义写反（示例/代码正确——记录不裁决）；④ 15s 预热判定仅正文未实现→归调用方；⑤ 页面默认 SDA=PB8/SCL=PB9 | `init()/read(uint16_t *tvoc_ppb, uint16_t *co2_ppm)` |
| pca9685 | 0x40（0x80/0x81），12bit PWM，芯片内部振荡 | ① **两套角度映射不一致**：setAngle 158+2.2× vs Init 145+2.4×——统一照 mspm0（0.5-2.5ms 脉宽→0-180°）；② main 60Hz vs 正文 50Hz→默认 50Hz（mspm0 同）；③ delay_1ms(5)/(100) 库内无；④ NACK 全丢；⑤ 正文频率公式 (50+1) 错误（代码正确）；⑥ Excel FLOOR 注释污染；⑦ 页面直接控角度（API 保留 set_pwm+set_angle 两级，角度层归一） | `init(freq_hz)/set_pwm(ch,width)/set_angle(ch,angle)/set_freq(freq_hz)/set_address(a5)` |
| hx711 | GPIO 双线 SCK/DT，24bit 有符号补码 | ① **`while(DT_GET());` 无界轮询**→20ms 超时（mspm0 先例）；② 全局泄漏（HX711_Buffer/Weight_*/Flag_Error 死变量）→收敛；③ **GapValue 207.00 演示校准常数**→参数化（照 mspm0）；④ 24bit 补码 `^0x800000`（mspm0 同款）；⑤ 「查看资料」节空 | `init()/tare()/read_raw()/get_gram()→float` |

⑤ **地址冲突裁决（spec 拍板）**：pca9685 0x40 × 批次 2 sht20 0x40 同址——pca9685 A5 引脚（set_address(a5)：0x40/0x41 二选）或同选时绑定换独立总线；sht20 地址不可改。默认两者各自合法（不同选即无冲突），notes 明示「同选时 pca9685 set_address(1)（0x41）或绑定换线」；不强制裁决（mspm0 侧同记录）。

⑥ **词表**：六件 slug 已挂接 wordlist（mspm0 批入库时——复核 lib_modules 命中），零补录；依赖 ["delay"/"adc"] 按 mspm0 模块级现状复制（ads1115/tcs34725/mlx90614/sgp30/pca9685 依赖 ["delay"]；hx711 依赖 ["delay"]——以 mspm0 manifest 现状为准）。

### 共性（七件一致——含回修工单）

1. 仅 stm32 条目（全 A 类；mspm0 零改动——**回修工单 01 除外**：只动 stm32 实现文件）；verified 初 false（回修件保持 true，notes 追加）；hardware_bound false；未上板 notes。
2. 代码提炼：手册「代码块」抽 bsp → `<slug>_init()` + 服务函数（**与 mspm0 完全对齐**：同函数名/同签名/同失败码/同出参单位）；去 main/printf/board_init/uart1_init；全局收敛 static；ADR 0009。
3. 换算：StdPeriph → ml_*（映射表同批次 2）；模块内零寄存器级/标准库调用；**I2C 件 SCL 初始化 OUT_OD（回修口径）**。
4. 引脚宏参数化：4 宏/件（逐脚端口宏）；manifest pins 4 行（I2C 件 id `<SLUG>_SCL/_SDA` type i2c_scl|i2c_sda；HX711 id `HX711_SCK/DT` type gpio_out|gpio_in）；零引脚字面量；默认脚 = 共总线 PA6/PA7（I2C）/PB5+PB0（HX711），重叠对登记 test_default_layout 白名单。
5. 时序：软 I2C 位操作忙等走 delay 模块；不占 TIMER、不注册中断（轮询；pca9685 芯片内部振荡零 MCU 时序）。
6. 测试：test_module_<slug>.py（照 test_module_aht10.py 模板）+ **SCL OUT_OD 初始化 guard**（I2C 件）+ 缺陷防回潮守卫（按各件列）+ STM32_MACRO_VALUES 24 宏 + test_default_layout 白名单（PA6/PA7 组新增 + PB5/PB0 组）。
7. 编译矩阵：UV4 0 error/0 module warning（MAIN_C 调 init+全部服务函数 (void) 化）→ verified=true。

## 测试决策

- 新增 `tests/test_module_ads1115.py` / `test_module_tcs34725.py` / `test_module_mlx90614.py` / `test_module_sgp30.py` / `test_module_pca9685.py` / `test_module_hx711.py`（照 test_module_aht10.py 模板：manifest 形状/宏存在/stm32 单选生成全流程/**mspm0 单选零改动守卫**/缺陷防回潮守卫/零标准库守卫）。
- **SCL 守卫（核心新增）**：每个 I2C 件测试断言 `gpio_init(<SLUG>_SCL_GPIO, <SLUG>_SCL_PIN, OUT_OD)` 文本在 init 中（防批次 2 式缺陷回潮）。
- 各件缺陷守卫示例：ads1115 `* 0.000125f` + 无 `65535`、tcs34725 `rgb_to_hsl` 内 `c == 0` 防护 + `||`、mlx90614 `* 0.02f - 273.15f` + 无 PEC/`PEC_Calculation`、sgp30 CRC8 `0x31`/`0xFF` + 读满 6 字节、pca9685 无 `delay_1ms` + 角度映射单式（无 `* 2.2f`/`* 2.4f` 双式）、hx711 超时 `20`ms + 无 `while (DT_GET` 无界式 + `^ 0x800000`（或 mspm0 同款补码表达式）。
- `tests/test_pins.py` STM32_MACRO_VALUES 补 24 宏（5 件 I2C ×4 + HX711 ×4）；test_default_layout.py 白名单：PA6/PA7 组 +5×2（I2C 件）、PB5 +1（HX711 SCK 叠 MOTOR_A_ENC）、PB0 +1（HX711 DT 叠 MOTOR_B_DIR）。
- **回修工单 01 测试**：六件 test_module_*.py（批次 2 的）追加同一 SCL OUT_OD 守卫（或统一文本守卫），六件矩阵复跑 0/0。
- UV4 矩阵（每件）：照 run_aht10_matrix.py 配方。

## 范围外

- mspm0 条目改动（仅 stm32；回修也只动 stm32 实现）；B 类新模块；C 类核对（批次 11）。
- 母版 ml_i2c 改造（继续不做）。
- 上板真机验证（未上板 notes——软 I2C 时序/CRC/温度换算走真机验证阶段；**批次 2 回修后真机验证一并安排**）。
- MLX90614 PEC/温补/发射率修正（mspm0 同款范围外）；SGP30 基线/自检/湿度补偿；ADS1115 比较器/ALERT；TCS34725 中断；PCA9685 频率模式枚举（API 有 set_freq）；HX711 自动标定（GapValue 参数化 + 手动校准流程归骨架）。
- pca9685 × sht20 同址冲突不再裁决（set_address 已提供，notes 明示）。

## 补充说明

- 排序：01 回修（打样先修）→ 02 ads1115 → 03 tcs34725 → 04 mlx90614 → 05 sgp30 → 06 pca9685 → 07 hx711；六件独立可并行（回修与六件同批，互不阻塞——本批 I2C 件实现时即按正确样式，不依赖回修完成）。
- 页内事实 = %TEMP%\batch3-facts.md（511d6150 研究报告，2026-09 已回填本表）。
- 收尾清单（全批完成）：全量 pytest+node:test → 一致性快检（sweep 更新）→ code-review 两轴 → CONTEXT.md 平台行补录批次 3 块 → 中文提交。
- **code-review 两轴结果（2026-09 收尾）**：Standards 轴（子代理报告）——**0 硬违反**（语言规范（spec/工单/15 条提交/CHANGELOG 全中文；本批零 .ps1，BOM 规则无涉；新 .c/.h UTF-8 无 BOM）、工单格式（`**状态：** resolved` 英文标签值 + 结论回填）、ADR 0009（纯驱动切片，六件均无状态机/调度）、ADR 0011（逐脚 4 宏 + pin_config.h 单源，11 件 I2C SCL OUT_OD+置高全核验）全部通过）；判断项 5 条：① **send_ack 参数名不一致（本批回潮）**——sgp30/pca9685 用 `ack`、其余三件用 `is_nack`——**已统一为 `is_nack`**（批次 2 收尾同口径，两件矩阵复跑 exit 0）；② Duplicated Code（五件 I2C 原语族逐件复制）——spec 决策①「自实现静态原语、不自建共享库」明文拍板，仓库标准优先，仅记维护成本；③ Shotgun Surgery（默认脚 PA6/PA7 推理散布 ~15 处联动）——已知成本（批次 2 已记）；④ Primitive Obsession 边缘（ads1115_read 失败返 0 与合法读数 0 混用）——spec「照 mspm0」拍板；⑤ 整洁度：`git diff --check` 报 6 个回修矩阵脚本 EOF 多余空行——**已清理**；另记录注释口径小项（2us≈100kHz vs ≈250kHz 不一、pca9685_set_address 超界静默钳位）。Spec 轴（子代理报告）——**实现与 spec 高度一致，零范围蔓延**：15 提交（回修 01 + 六模块 + 自动 CHANGELOG）无多余；SCL 守卫 grep 11 文件（批次 2 六件全部 + 批次 3 五件 I2C 件；hx711 为 GPIO 双线件不涉 SCL——与工单相符）；sweep_7_modules.py 6/6 OK；六件 manifest stm32 均 verified=true/hardware_bound=false/顶层 dependencies=["delay"]/source_url wiki 原页；pin_config.h 批次 3 宏齐备；API 对齐六件 mspm0/.h 与 stm32/.h slug 前缀函数集合完全一致（双边零独有项）；缺陷修正标记全部命中（ads1115 32768.0f*fsr、tcs34725 c==0/|| 判 ID（无 ` == | `）、mlx90614 *0.02f-273.15f（零 PEC）、sgp30 读满 6 字节+0x31u/0xFFu+return 5、pca9685 0.0005f/0.0025f（无 delay_1ms/*2.2f/*2.4f）、hx711 ++timeout>2000/^0x800000u/HX711_GAP_VALUE（无 HX711_Buffer））；「不应含」令牌仅存在于缺陷说明注释，代码零残留。两处清单措辞 vs schema 差异（dependencies 顶层 vs 工单写 stm32 段、pins=2 信号脚不列 VCC/GND）系批次 2 同构先例，非缺陷。
