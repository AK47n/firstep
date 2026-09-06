# 批次 2「软 I2C 总线件」— 立创 wiki 地阔星 STM32F103C8T6 手册模块批量入库（stm32 线）

## 问题陈述

stm32 线现状：84 模块中 61 个 mspm0 单平台件（地图定稿 A 类），批次 1（wiki-stm32-batch1/01-06，GPIO 迷你件）已打通管线并入库 6 件；剩余 mspm0 单平台件中仍有大量「总线器件」——温湿度/光照/气体/EEPROM 等软 I2C 件——在 stm32 生成时全部报 missing 警告，用户做 STM32 工程时这些传感器只能「需自备」。

本批 = **批次 2「软 I2C 总线件」**：6 件全为软 I2C 形态（2 × GPIO 位操作，SDA 方向运行时切换——不占硬件 I2C 外设、不占 TIMER），页面驱动 4-6 块（比批次 1 迷你件大：地址/命令字/回包/换算/CRC），用它们把 stm32 线「软 I2C 换算 + 多件共总线」模式打样。layout 含：

| 件 | 页面 | 形态 | 器件地址 | 回包 | 备注 |
|---|---|---|---|---|---|
| aht10 | sensor--aht10-temp-humi-sensor.md | i2c_scl/i2c_sda | 0x38 (0x70/0x71) | 6B 温湿度 20bit | mspm0 先例最全 |
| bh1750 | sensor--bh1750-light-intensity-sensor.md | i2c_scl/i2c_sda | 0x23 (0x46/0x47) | 2B 光照 16bit | 无 CRC、命令序列最简 |
| sht20 | sensor--sht20-temp-humi-sensor.md | i2c_scl/i2c_sda | 0x40 (0x80/0x81) | 2B×2 温/湿 | 状态位掩码修正 |
| sht30 | sensor--sht30-temp-humi-sensor.md | i2c_scl/i2c_sda | 0x44 (0x88/0x89) | 6B + CRC8×2 | 周期模式 + CRC |
| at24c02 | control--at24c02-eeprom-memory.md（**control 目录**） | i2c_scl/i2c_sda | 0x50 (0xA0/0xA1) | 字节/页写/连续读 | **EEPROM 读写件：API 面最宽** |
| ags10 | sensor--ags10-harmful-gas-sensor.md | i2c_scl/i2c_sda | 0x1A (0x34/0x35) | 5B 24bit TVOC + CRC8 | 页面返回码混用缺陷 |

## 方案

照批次 1 已确立管线，每件一个工单：手册「代码块」提炼完整驱动（正文内嵌段落禁用）→ 纯驱动切片改造（去 main/printf、API 规范化、ADR 0009 无状态机、页面 bug 人工复核修正+notes+守卫）→ **F1 标准库软 I2C → 母版 ml_* API 换算**（GPIO_Init→gpio_init、GPIO_WriteBit/SetBits/ResetBits→gpio_set、GPIO_ReadInputDataBit→gpio_get、delay_us/ms 同名；页面位操作原语族按 mspm0 版结构静态化重写：**SDA 方向运行时切换 = gpio_init 重配（OUT_PP→IF）**，不用母版 ml_i2c（见实现决策①）→ 母版 `pin_config.h` 新宏段（`_GPIO/_PIN` 尾形，pinwriter 8 尾形支持内）→ manifest stm32 条目（files/pins+macros/verified 初 false/kit+source_url=wiki 原页/notes 含手册路径+网盘+改造要点+修正记录）→ 测试（新增 test_module_<slug>.py 照 test_module_relay.py 模板 + test_pins/test_default_layout 同步）→ **UV4 单选编译矩阵 0 error/0 module warning 硬门槛**（`C:/Keil5/Core/UV4/UV4.exe`，`-j0 -r -b`）→ verified 回写 → 中文提交 → 工单 resolved。

## 用户故事

1. 作为做题用户，我选 stm32 平台 + aht10/sht20/sht30/bh1750/ags10 后，生成工程打开即可编译，`<slug>_init()` + `<slug>_read()` 直接读温湿度/光照/TVOC（出参带回，不再「需自备」）。
2. 作为做题用户，我选 stm32 + at24c02 后，`at24c02_write_byte/read_byte/write_page/read_block/wait_write_done` 掉电保存参数（页写 16 字节、跨页拒收、写周期 5ms 等待），不再「需自备」。
3. 作为做题用户，我一次选多个总线件（如 aht10+bh1750+at24c02 环境记录站）：六件默认共挂**同一总线**（PA6 SCL/PA7 SDA，器件地址全异、多挂合法）→ 开箱即用零改线；与其它模块同选冲突时 UI 标 ⚠、经引脚绑定换脚消解。
4. 作为维护者，查看每个新条目能看到 stm32 平台条目（verified/kit/source_url=wiki 原页/notes 含手册路径+原页+网盘+换算要点+页面缺陷修正记录），可溯源到地阔星页面。

## 实现决策

### 既定事实（勿重新调研；本次调研实证，模块库现状读盘复核为准）

① **软 I2C 换算方案拍板：自实现静态原语（mspm0 先例），不用母版 ml_i2c 原语**——三理由：
   - ml_i2c（I2C_Init/Start/Stop/SendByte/ReceiveByte/SendAck/NotSendAck/WaitAck）**零延时位操作**（ml_i2c.c 无任何 delay 调用，72MHz 裸跑总线频率远超六件规格上限——AGS10 规格甚至 ≤15kHz；母版头注释仅「需将对应引脚配置成开漏输出」，无时钟标注）——真机功能风险，不能作为六件的通信底座；
   - ml_i2c 引脚硬绑 `I2C_GPIO/I2C_SCL/SDA_GPIO_Pin` = **PA11/PA12（USB 共用脚）**——本批六件默认脚若不照抄页面、又复用它 = 与板载 USB 固定资源冲突风险（板定义 fixed 明示「用 USB 时勿占用」，且与 mspm0 版各自独立默认脚的同构先例不符）；
   - 母版 ml_i2c 无 SDA 方向运行时切换（单 OUT_OD 模式 + IDR 读）——本批六件 mspm0 版 API 全为「2 GPIO + SDA 方向切换」形态，API 对齐（同函数名/同语义）要求 stm32 侧同构。
   → 每件模块内静态 `_iic_*` 原语族（照 mspm0 版逐函数镜像：start/stop/send_ack/wait_ack/send_byte/read_byte），SDA_OUT/SDA_IN = **页面原式**（`GPIO_Mode_Out_OD` 开漏输出 / `GPIO_Mode_IPU` 上拉输入 → ml_gpio `OUT_OD`/`IU`；stm32 侧 SDA 方向切换 = gpio_init 重配——页面与 mspm0 版同为「写=输出驱动、读=输入采样」形态，仅 OD/IU 与推挽/浮空的差异（语义等价、均需总线外上拉，页面真机验证过、按原式））；SDA_GET = `gpio_get`、SCL/SDA 电平 = `gpio_set`；时序常量 = mspm0 版同值（= 页面原值：aht10/bh1750/at24c02 半周期 2-4us、sht20/sht30/ags10 半周期 5us ≈ 100kHz 级，规格 400kHz（AGS10 页面规格 15kHz 但与页面代码矛盾——按页面代码，真机异常调慢，notes））；延时走 delay 模块（依赖 ["delay"] 已存在，模块级共享零改动）。**模块代码零 ml_i2c 调用、零寄存器级/标准库调用**。

② **引脚宏设计（独立宏段，逐脚端口宏）**：每件 4 宏——`<SLUG>_SCL_GPIO/<SLUG>_SCL_PIN/<SLUG>_SDA_GPIO/<SLUG>_SDA_PIN`（照 stm32 UART 引脚宏 `DIGIT_UART_TX_GPIO/TX_Pin` 先例，非「I2C_GPIO 单端口宏 + 双 PIN」）。理由：a) 避免共享端口宏（同期六件若同 `_GPIO` 宏，绑定时 ADR 0011 异值 400 会把六件捆死）；b) 逐脚独立绑定（SCL/SDA 可分属不同端口——mspm0 版 ags10 就是跨口 PB18/PA14 先例，无同口约束）；c) 与既有 `I2C_GPIO`（PA11/12，ml_mpu6050 用）/`OLED_GPIO`（PB8/9，ml_oled 用）两段**互不重叠、独立并存**——同选 mpu6050/oled + 本批件 = 三条总线各自独立（地址不同、物理不同），合法。

③ **引脚角色类型 = `i2c_scl` / `i2c_sda`**（stm32 侧，ml_mpu6050.MPU6050_SCL/SDA 先例）——不是 mspm0 侧的 gpio_out（mspm0 侧因 syscfg GPIO 实例语义用 gpio_out；stm32 侧 i2c token 去实例 = 任意 io，`_shared_groups` 判据：同脚全为 i2c_* 类型 = 「I2C 总线共享」合法（六件共总线标注正当），与他人（gpio_out 等）同脚 = 「同引脚但分属不同外设」冲突 ⚠（与本批默认重叠语义一致）；引脚 id = `<SLUG>_SCL/<SLUG>_SDA`（对偶 mspm0 同名，成对校验 `_SCL/_SDA` 尾形根配对——stm32 无实例集 = 防御路径不查，放宽）。

④ **默认总线 = PA6 (SCL) / PA7 (SDA)，六件共挂**（`同选概率最低`推理）：
   - F103C8T6 排针 32 脚全被既有默认占用（批次 1 现状 + 本批无空闲——板定义复核：BOOT1=PB2 未引出，PA13/14 SWD，PA11/12 USB，晶振 PD0/1）；
   - 六件 = 环境传感/存储记录类（温湿度/光照/气体/EEPROM），主框 = **环境监测站/数据记录仪**（常配 OLED 显示、按键/蜂鸣报警、LED、继电器联动、无线链路、调试串口）；
   - 同选概率低→高：电机方向（PA6/PA7、PB0/PB1）＜ 编码器（PA4/PB5）＜ 舵机/巡线（PB6/PB7）＜ 传感件（PA5 flame、PA8 ir_beam/ws2812、PB7 human_ir）＜ 显示/声光/输入/无线（PB8/9 OLED、PC13-15 LED、PA15 蜂鸣、PB3 按键、PB10/11 zigbee、PA9/10 UART1、PA11/12 USB、PA2/3 DEBUG）；
   - **PA6/PA7 重叠主体 = motor MOTOR_A_DIR/DIR2（TB6612 A 相方向，GPIO 输出）**——「带电机方向的小车型运动控制」与本批环境传感/记录不同框（小车题几乎不选软 I2C 六件，环境站题不带电机方向）；PA6/7 非显示/声光/按键/串口脚、无 EXTI 默认注册（轮询不注册中断）；PA6/7 = TIM3_CH1/2、ADC CH6/7 备用能力（未被任何默认占用，绑定层消解）。
   - 页面默认脚**全部不照抄**（页面 F1 标准库宏默认各不同——见各件决策表；均与既有占用互抢，按批次 1 定论「互抢且全中既有占用」）。
   - 与既有 I2C_GPIO（PA11/12）/OLED_GPIO（PB8/9）段关系：零重叠、独立并存——同选 mpu6050/oled + 本批 = 三总线独立（USB 保持空闲，本批不用 PA11/12）。
   - **多件共总线合法共享**：六件地址 0x38/0x23/0x40/0x44/0x50/0x1A 全异，SCL/SDA 同口（PA6/PA7 同 GPIO_A——排针连线整组 4P 头贴邻），test_default_layout 白名单 PA6/PA7 组登记（见测试决策）。
   - 同选冲突消解：与 motor 同选时经引脚绑定换脚（pinwriter 行级覆写各件 `_GPIO/_PIN` 宏）；六件默认互为总线共享、无需消解。

⑤ **测试接缝（stm32 侧，批次 1 已实测）**：test_pins.py STM32_MACRO_VALUES 钉值表补 24 宏；test_default_layout.py 白名单 PA6/PA7 组（六件 × 2 角色 + motor 2 角色）；test_module_<slug>.py 照 test_module_relay.py 模板（manifest 形状 + 宏存在 + stm32 单选生成全流程 + mspm0 单选生成零改动守卫 + 页面缺陷防回潮守卫）。

⑥ **编译矩阵**：照 batch1 `run_relay_matrix.py` 配方（resolve_selection→generate→collect_build_log(uv4=find_uv4())→compile_passed exit 0 + 0 module warning 硬门槛；MAIN_C 调 init+全部服务函数 (void) 化；产物 .scratch/wiki-stm32-batch2/matrix/<slug>/）。

⑦ **来源标注**：source_url = 地阔星 wiki 原页（`https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/<cat>/<slug>.html`）；notes = 手册路径（`sources/materials/lckfb-地阔星移植手册/<cat>--<slug>.md`）+ 原页 + 网盘 + 采购 + 换算/修正要点 + 未上板；kit = 页面「模块来源」套件名。

⑧ **词表**：六件 slug 已挂接 wordlist（mspm0 批入库时——复核 lib_modules 命中 aht10/bh1750/sht20/sht30/at24c02/ags10），零补录（批次 1 同口径）；依赖 ["delay"] 模块级已有，零改动。

### 共性（六件一致）

1. **仅 stm32 条目**（全 A 类：mspm0 条目已存在，零改动）；verified 初始 false，UV4 矩阵 0/0 过 → true；hardware_bound false；未上板（notes）。
2. **代码提炼**：手册「代码块」抽 bsp_xxx.c/.h → `<slug>_init()` + 服务函数（**API 与 mspm0 版完全对齐：同函数名/同语义/同失败码**——见各件决策表）；去 main/printf/board_init/uart1_init；全局收敛模块内 static；ADR 0009 无状态机。
3. **换算**：StdPeriph → 母版 ml_* API（映射表：GPIO_Init→gpio_init、GPIO_WriteBit/GPIO_SetBits/GPIO_ResetBits→gpio_set、GPIO_ReadInputDataBit→gpio_get、GPIO_Speed/结构体字段→ml_gpio 内定、RCC_APB2PeriphClockCmd→gpio_init 内部使能、delay_us/ms 同名、iic 原语族→按 mspm0 版结构静态化重写）；模块内零寄存器级/标准库调用。
4. **引脚宏参数化**：manifest pins（id/type i2c_scl|i2c_sda/default PA6|PA7/required true/macros 4 条）；模块 .c/.h 零引脚字面量（test_pins 门禁自动覆盖）；默认脚 = 总线共享 PA6/PA7（同选概率最低 + 共总线合法共享），重叠对登记 test_default_layout 白名单（注释理由/批次号）。
5. **极性**：总线协议无极性归一化需求（I2C 电平=标准），无单宏极性件。
6. **时序**：软 I2C 位操作忙等走 delay 模块（delay_us/ms，SysTick 忙等——与 ml_systick 无冲突先例 ws2812）；不占 TIMER、不注册 GPIO 中断（轮询）。
7. **wordlist**：零补录（已挂接）。

### 各件决策（2026-09 回填，页内事实已取证——batch2-facts.md；全部六页 = F1 标准库，无 F4 嫌疑页；页面默认脚全为 GPIOB8/PB9（与母版 OLED 段重叠）——全部不采用，默认 PA6/PA7 共总线）

| 工单 | slug | 手册 | 器件地址 | 母版 pin_config.h 宏段 | API（与 mspm0 对齐） | 页面缺陷（修正+notes+守卫） |
|---|---|---|---|---|---|---|
| 01 | aht10 | sensor--aht10-temp-humi-sensor.md | 0x38（0x70/0x71） | `AHT10_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN` | `aht10_init`（50ms+校准 0xE1 0x08 0x00）+ `aht10_read(t,h)`（0xAC 0x33 0x00 → 20ms+5×1ms 重试 → 6B；湿度 = ((b1<<12)|(b2<<4)|(b3>>4))/1048576×100、温度 = (((b3&0x0F)<<16)|(b4<<8)|b5)/1048576×200−50；0=成功/1=超时）+ read_temperature/humidity | ① 每读后重复复位+初始化（AHT10Reset 0xBA + 0xE1 校准——~100ms 冗余）→ 合并 init；② init 连发无应答检查 → 补 wait_ack；③ 读地址重试超时不判失败 → timeout>=5 return 1；④ 注释与值矛盾×3（L339 读地址注释/L358 ack 注释/L298 获取状态注释）；⑤ char→uint8_t + 死变量；**已知偏差**：窗口 20ms+5×1ms ≪ 手册 ≥80ms（页面/mspm0 原式保留，真机失败单点调大） |
| 02 | bh1750 | sensor--bh1750-light-intensity-sensor.md | 0x23（0x46/0x47，ALT 接地） | `BH1750_*` | `bh1750_init`（0x01 上电+引脚 OD/置高）+ `bh1750_start_measure`（0x10 连续高分辨率；0/1）+ `bh1750_read_lux(lux)`（0x47 → 2B 高前低后 → /1.2；0=成功/1=无应答）+ `BH1750_MEASURE_DELAY_MS 140` | ① 读路径 WaitAck 丢弃（L306）→ 检查返回 1；② 模板串台（L93「MLX90614的引脚初始化」）；③ BUF[8] 死全局 + 注释块函数名缺后缀（不落）；④ 规格 1~65536 vs 正文 0-65535（记录不裁决）；⑤ main 180ms 硬编码 → 140 宏（等待归调用方） |
| 03 | sht20 | sensor--sht20-temp-humi-sensor.md | 0x40（0x80/0x81） | `SHT20_*` | `sht20_init`（空占位——单次模式无预置命令；引脚配置由 init 完成）+ `sht20_read(t,h)`（0xF3/0xF5 两段各：写地址→命令→读地址重试 ≤50×2ms→2B+NACK→raw&0xFFFC；温度 = raw/65536×175.72−46.85、湿度 = raw/65536×125−6；0=成功/1=温度段失败/2=湿度段失败） | ① do-while 裸轮询无上限 → ≤50×2ms（100ms 窗口覆盖 85ms/29ms）；② **状态位未掩码**（正文要求 &0xFFFC、代码未做——SHT2x 手册修正）；③ 0xE3/0xE5（hold）注释 vs 0xF3/0xF5 代码三方矛盾——采信代码；④ 应答失败仅 printf 后继续 → 失败码 1/2；⑤ char 死变量；**同址提醒**：pca9685 0x40（共总线双选冲突须错开） |
| 04 | sht30 | sensor--sht30-temp-humi-sensor.md | 0x44（0x88/0x89，ADDR 接地） | `SHT30_*` | `sht30_init`（0x2130 周期模式）+ `sht30_read(t,h)`（0xE000 → 读地址重试 ≤20×2ms → 6B + CRC8（0x31/0xFF）双组 → 温度 = d/65535×175−45、湿度 = d/65535×100；0=成功/1-5 页面失败码）+ read_temperature/humidity | ① 串台 L44「ADS1115是采用的IIC通信」（不落）；② **extern double 页外泄漏**（.h L427——全批唯一）→ float 出参；③ 命令表 0x2126 vs 代码 0x2130（两值皆合法——采信代码）；④ crc8 通用名非 static + `#define u8` 污染 → 静态化+uint8_t；⑤ char 死变量 + 校验失败 printf → 剔除（返回 5）；⑥ IIC_Start 多余 Stop→Start 边沿（按页面原样保留）；**电平配置 = 全批唯一推挽+浮空（PP+IF）**——工作前提 = 模块自带上拉 |
| 05 | at24c02 | control--at24c02-eeprom-memory.md（**control 目录**） | 0x50（0xA0 写/0xA1 读） | `AT24C02_*` | `at24c02_init`（空占位；引脚配置由 init 完成）+ `at24c02_write_byte`（void 页面原式）+ `at24c02_read_byte`（伪写定位；无应答返回 0xFF）+ `at24c02_wait_write_done`（~5ms）+ `at24c02_write_page`（≤16B 页内、跨页拒收；0/1/2）+ `at24c02_read_block`（连续读：首字节 ACK 末字节 NACK、256 边界翻转；0/1/2） | ① **地址宏名颠倒（主缺陷）**：READ 宏挂 0xA0（写）/WRITE 宏挂 0xA1（读）——命名纠正、值保留；② 读写路径应答全丢弃（WriteByte/ReadByte 页面原式保留——调用方先写后读验证；write_page/read_block 补 2=无应答）；③ 注释 48/66 不符（不落）；④ %d 打 unsigned char（不落）；⑤ 写周期 5ms 未封装 → wait_write_done；⑥ 页写/连续读正文有述、代码未实现 → 按正文补齐 |
| 06 | ags10 | sensor--ags10-harmful-gas-sensor.md | 0x1A（0x34/0x35） | `AGS10_*` | `ags10_init`（空占位——无初始化序列，预热 ≥120s 归调用方；引脚配置由 init 完成）+ `ags10_read(voc_ppb)`（写 0x00 → 读 0x35 重试 `timeout<50×1ms` → 5B = 状态+TVOC 24bit+CRC → CRC8 校验 → TVOC = (d1<<16)|(d2<<8)|d3 ppb；0=成功/1=通信失败/2=发送失败/3=等待超时/4=校验失败） | **全批最重（9 条）**：① **读地址重试条件写反（致命）**`(timeout >= 50)`——循环一次即退、return 3 永不触发 → `timeout < 50`；② **返回码与 TVOC 值混用**（TVOC=1ppb 与「通信失败」不可分）→ 出参+状态码；③ delay_1us/delay_1ms 库内不存在 → delay_us/ms 改写；④ 规格 ≤15kHz vs 代码 100kHz（按代码 + 唯一时序宏点）；⑤ 注释掉 printf（不落）；⑥ char 死变量；⑦ Send_Nack/Ack 冗余二次写（页面原式保留）；⑧ main 未等预热/1s 采样 <2s（演示不落）；⑨ 状态字 data[0] 未使用（读入不检查） |

### 默认脚与重叠全景（定稿）

| slug | 默认脚 | 重叠主体（同选概率最低） |
|---|---|---|
| `aht10` | SCL=PA6 / SDA=PA7 | MOTOR_A_DIR/DIR2（电机方向——环境传感与「带方向的小车运动控制」不同框；六件共总线） |
| `bh1750` | SCL=PA6 / SDA=PA7 | 同上（共总线合法共享：地址 0x23 与其它五件全异） |
| `sht20` | SCL=PA6 / SDA=PA7 | 同上（共总线；地址 0x40 与 pca9685 同址——notes 提醒，共总线同选注意） |
| `sht30` | SCL=PA6 / SDA=PA7 | 同上（共总线） |
| `at24c02` | SCL=PA6 / SDA=PA7 | 同上（共总线；存储记录与传感同站常见组合，合法共挂） |
| `ags10` | SCL=PA6 / SDA=PA7 | 同上（共总线；气体+温湿度+光照 = 空气质量站常见组合） |

- **六件默认互撞 = 总线共享**（PA6 七角色/PA7 七角色，全 i2c_* 类型 → `_shared_groups` 判 kind=share「I2C 总线共享」——多挂协议允许，无需消解）；登记 test_default_layout 白名单（注释理由/批次号/总线共享语义）。
- 与既有默认重叠计数（白名单新增 2 组）：PA6 +6（六件 SCL，同 MOTOR_A_DIR）、PA7 +6（六件 SDA，同 MOTOR_A_DIR2）。
- 消解机制：**六件与 motor 同选时经引脚绑定换脚**（pinwriter 行级覆写各件宏——逐脚端口宏无共享宏异值 400 风险；六件仍可共挂新总线）；六件之间永不冲突（同一总线=同一物理线，无需消解）。

## 测试决策

- 新增 `tests/test_module_aht10.py` / `test_module_bh1750.py` / `test_module_sht20.py` / `test_module_sht30.py` / `test_module_at24c02.py` / `test_module_ags10.py`（照 test_module_relay.py 模板）：
  1. manifest 形状：platforms 含 stm32（mspm0 条目原样）、files 逐个存在、pins 元组 (id,type=i2c_scl|i2c_sda,default=PA6|PA7,required,macros=(4 宏))、kit+source_url=wiki 原页、notes 关键子串（手册路径/未上板/页面缺陷修正记录）。
  2. 母版宏存在断言：pin_config.h `#define <MACRO>` 正则（SCL_GPIO GPIO_A / SCL_PIN Pin_6 / SDA_GPIO GPIO_A / SDA_PIN Pin_7）。
  3. **stm32 单选生成全流程**：resolve_selection + generate → `modules/<slug>/code/<slug>_stm32.c` 落盘 + `.uvprojx` modules 组含 .c + pin_config.h 在工程根。
  4. **mspm0 单选生成零改动守卫**（mspm0 侧仅加断言文件仍在）。
  5. 页面缺陷防回潮守卫（按各件列：如 sht20 `& 0xFFFC`、sht30 CRC 多项式 0x31 初值 0xFF、at24c02 地址 0xA0 写/0xA1 读命名、ags10 `timeout < AGS10_RETRY_MAX` / 出参+状态码、bh1750 0x10 start_measure、aht10 0x70 原式）。
  6. 零引脚字面量/零标准库守卫（BANNED_CODE_PATTERNS：printf/main/board_init/GPIO_Init/RCC_/stm32*.h + 无 ml_i2c 调用——本批自实现原语族）。
- `tests/test_pins.py`：STM32_MACRO_VALUES 补 24 宏（AHT10/BH1750/SHT20/SHT30/AT24C02/AGS10 × SCL_GPIO/SCL_PIN/SDA_GPIO/SDA_PIN = GPIO_A/Pin_6/GPIO_A/Pin_7）；其余测试自动覆盖新声明（宏存在/默认脚板上+能力/零字面量）。
- `tests/test_default_layout.py` 白名单：PA6/PA7 两组（六件 SCL/SDA + motor MOTOR_A_DIR/DIR2；注释批次 2 + 总线共享语义）。
- **UV4 编译矩阵**（每件）：照 run_relay_matrix.py 配方（MAIN_C 调 init+全部服务函数并 (void) 化——aht10 带 float 出参、sht30 带 read_temperature/read_humidity、at24c02 带 write_page/read_block 验证分支、ags10 带 uint32_t 出参）→ 0 error/0 module warning → verified=true + notes 回写。
- 词表预算链：六件零补录（已挂接 mspm0 批），无预算链动作（实测复核即可）。

## 范围外

- mspm0 条目改动（本批 A 类仅补 stm32；mspm0 侧零改动）；B 类新模块；C 类核对（批次 11）。
- 上板真机验证（未上板，notes 注明——软 I2C 时序 100kHz 级/测量等待/CRC 真机验证留后续）。
- 母版 ml_i2c 改造（加延时/引脚参数化 = 母版功能库改动，本批不做；ml_i2c 现状注释说明）。
- 页面「与 DHT11 相同」指引句不提炼；演示 main 不提炼；硬件 I2C 外设不启用（全部软 I2C）。
- AGS10 ≤15kHz 规格时序微调（按页面代码实现，真机异常才调——notes 给唯一时序宏点）。
- 总线地址冲突裁决（sht20×pca9685 同址 0x40——即存在，notes 提醒不裁决）。

## 补充说明

- 排序：01 aht10（mspm0 先例最全、打样件）→ 02 bh1750（命令序列最简，练手）→ 03 sht20（状态位掩码修正 → 04 sht30（CRC 件）→ 05 at24c02（EEPROM 读写件，API 最宽）→ 06 ags10（CRC + 返回码混用缺陷，最重）。
- 页内事实（代码块结构/F1/F4/极性/缺陷/API 对照）= 研究子代理报告（%TEMP%\batch2-facts.md，2026-09 已回填 spec 决策表 + 工单）。
- **code-review 两轴结果（2026-09 收尾）**：Standards 轴（子代理报告）——**0 硬违反**（语言规范/ADR 0009/0010/0011/批次 1 同构全部通过：纯驱动切片、零引脚字面量、零标准库/ml_i2c 调用、manifest 纯增量 mspm0 零改动、API 与 mspm0 同名同语义）；判断项 3 条：① send_ack 参数名不一致（aht10/sht20/sht30 用 `ack`、bh1750/at24c02 用 `is_nack`——后者更准确；已按 bh1750/at24c02 口径统一三件为 `is_nack` + 三矩阵复跑 exit 0）；② **aht10_stm32.h 注释「出参可传 NULL」与实现（`!= 0`）/F1 头无 NULL 矛盾——已修**（改「出参判空用 0——F1 头无 NULL」）；③ 六件原语族/pin_config 24 宏/测试 24 条重复（spec 决策①「自实现静态原语、mspm0 同构、不自建共享库」与批次 1 先例同判可接受——仅记维护成本：默认脚 PA6/PA7 知识散布 ~15 处联动（Shotgun Surgery 风险，spec 已明知，改默认脚走 spec 决策②逐处同步）。Spec 轴（子代理报告）——**实现与 spec 高度一致，零范围蔓延**（diff 零触碰 wordlist/ml_i2c/sources/materials/mspm0；pin_config.h 仅新增独立宏段；manifest 零删除行）：关键核查点全通过（ags10 `timeout < AGS10_RETRY_MAX` 修正/出参+状态码、sht20 `& 0xFFFCu` + ≤50×2ms、at24c02 0xA0 写/0xA1 读命名纠正 + wait_write_done + 跨页拒收、bh1750 读路径 wait_ack 检查 + 140 宏、aht10 init 合并复位 + `timeout>=5` return 1、sht30 `static uint8_t sht30_crc8` + return 5 + PP/IF 唯一一派、白名单 PA6/PA7 各 7 角色全登记、STM32_MACRO_VALUES 24 宏全钉值）；唯一提示 = 收尾项（CONTEXT.md 平台行补录 + sweep 脚本）随收口提交（已办）。
- 收尾清单（全批完成）：全量 pytest **3614 passed**（基线 3601 + 本批 +13）+ node:test **1359 passed**（`node --test "tests/js/*.test.mjs"`——Node 24 下 `node --test tests/js` 会把目录当模块报 MODULE_NOT_FOUND，须 glob 形式）→ 一致性快检 sweep_6_modules.py **6/6 OK**（含本批新增共总线不变量面：4 宏值/类型/默认脚/零 ml_i2c）→ code-review 两轴（0 硬违反 + 2 判断项整改）→ CONTEXT.md 平台行补录（stm32 线批次 2 块）→ 中文提交。
- **软 I2C 件 ≠ 母版 ml_i2c 消费者的判例**：本批六件各自静态原语（mspm0 同构）；ml_mpu6050（既有 stm32 件）继续走母版 ml_i2c（零改动）——两条路线并存，notes 分工记录。
- 收尾清单（全批完成）：全量 pytest + node:test → 一致性快检（照 batch1 sweep_6_modules.py 更新为 batch2 版：stm32 条目存在性/verified/hardware_bound/wordlist 挂接/source_url wiki 判据/依赖正检 + 六件宏一致/总线共享白名单）→ code-review 两轴 → CONTEXT.md 平台行补录（stm32 线批次 2 块）→ 中文提交。
