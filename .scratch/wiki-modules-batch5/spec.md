# 批次 5「I2C 增强件」— 立创 wiki 地猛星手册模块批量入库

## 问题陈述

批次 1「遥控/通信」（joystick/hc05/nrf24l01/ir_remote）、批次 2「传感器常用」（dht11/us016/bh1750/ir_distance）、批次 3「显示/执行」（max7219/pca9685/ir_remote_tx）、批次 4「语音/身份」（jq8900/syn6288/rc522/fingerprint）已入库。`lckfb-地猛星移植手册/` 剩余页中**I2C 增强**四篇页内自带完整驱动源码（v7 审计自包含）：ADS1115 四通道 16bit 外扩 ADC、TCS34725 颜色识别、MLX90614 非接触红外测温、AT24C02 EEPROM——模块库仍无对应条目：用户做多路模拟量采集/颜色识别/非接触测温/掉电数据存储题时，AI 不知道库里有驱动，只能当"需自备"。

按用户裁决：批次 5 = **I2C 增强件**四件——ADS1115、TCS34725、MLX90614、AT24C02——全部页内源码完整（v7 全自洽）、无需网盘。

## 方案

照批次 1-4 已确立管线，每件一个工单：手册「代码块」提炼完整 bsp（正文内嵌段落禁用）→ 纯驱动切片改造（去 main/printf、API 规范化、ADR 0009 无状态机——连续读多次/写入流程归生成骨架）→ 母版 syscfg 新 GPIO 实例 + `syscfg_instances.py` INSTANCE_CONSUMERS 登记 → manifest（dependencies/pins/kit+source_url/notes 含手册路径+原页+网盘链接+改造要点+与库内 adc 模块分工说明）→ wordlist.json 补录（感知传感器 + 存储/数据记录新分类，lib_modules 挂接）→ 测试（`test_module_<slug>.py` 照 test_module_joystick.py 模板 + test_pins.py / test_pin_bindings.py / test_syscfg_prune.py 增断言）→ 编译矩阵（复制 run_*_matrix.py 改 slug：单选生成 → SysConfig CLI → gmake 0 error/0 warning 硬门槛）→ verified=true 回写 → 中文提交 → 逐件 code-review。

## 用户故事

1. 作为做题用户，我选中 `ads1115`/`tcs34725`/`mlx90614`/`at24c02` 后，工具自动分配默认脚，生成工程打开即可编译，可调用 init + 服务函数。
2. 作为做题用户，我做多路模拟量采集（外扩 4 通道 ADC）、颜色识别（RGB/HSL）、人体/物体非接触测温、掉电数据存储（EEPROM 参数/记录）时，不用再读器件手册、不用自写 I2C 位操作。
3. 作为维护者，查看每个新条目能看到平台条目（verified/kit/source_url/网盘链接/改造要点/编译记录），可溯源到手册。

## 实现决策

### 既定事实（勿重新调研，批次 1-4 已实证）

① 母版 `ADC12_0` 已是 sequence 四通道（endAdd=3：MEM0=adc+us016 / MEM1-2=joystick / MEM3=ir_distance），本批不新增 ADC 件（软 I2C 只是 GPIO 实例，与 ADC12_0 无关）；② SysConfig 拒绝同一 UART 外设多实例（实例上限 4）——本批无 UART 件；③ 地猛星 2×20 排针 31 个 IO 全被默认布局占用——新模块默认脚按「同选概率最低者与既有默认重叠」，同选经引脚绑定消解；④ 母版 GPIO 中断全走 GROUP1 一个向量且被 KEY/motor 编码器消费——本批全部轮询，不注册中断；⑤ 软 I2C 先例 aht10（PB6/PB7）、pca9685（**PB6/PB7**，读 manifest 确认）——SDA 方向运行时切换；软 SPI 先例 nrf24l01/max7219/rc522；软 UART TX 先例 jq8900/syn6288；忙等不占 TIMER（TIMG0/6/7/8/12 全占）；⑥ 工具链 `C:/ti/ccs2050`、SysConfig CLI `C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat`；⑦ 页内符号异常人工复核（上游缺陷剔除并记 notes）。

### 共性（四件一致）

- **仅 mspm0 平台条目**（stm32 缺条目 = 生成时 missing 警告，批次 1 先例）；`hardware_bound: false`；`verified` 初始 false，编译矩阵通过转 true；未上板（notes 注明）。
- **代码提炼**：从手册「代码块」章节抽完整 bsp，改造为 `xxx_init()` + 服务函数，去 main/printf，函数名规范化（去 `WriteADS1115`/`AT24C02_WriteByte`/`TCS34725_GetRawData` 菜市场命名按库风格重命名——`ads1115_write_config` 等），全局状态收敛为模块内静态 + 出参指针（tcs34725 的 `extern COLOR_RGBC rgb` 全局收敛）。
- **软 I2C 原语静态化**：`iic_start/stop/ack/wait_ack/send_byte/read_byte` 照 aht10 先例（模块内 static `xxx_iic_*`，微秒/毫秒延时全走库内 `delay` 模块，`dependencies: ["delay"]`）；**不占 TIMER**；**不注册 GPIO 中断**。
- **引脚宏参数化**：按 manifest pins 角色 + 母版 syscfg 实例宏名对齐（`<实例>_<引脚>_PIN`/`_IOMUX`，SysConfig 命名 `<实例>_<引脚名>_IOMUX`，aht10 编译矩阵实测）；SDA 方向运行时切换（`SDA_OUT/IN` 宏照 AHT10_SDA 先例，`DL_GPIO_initDigitalOutput/Input` 由驱动调用）。
- **默认脚**：按「同选概率最低者与既有默认重叠」分配；**四件互为最常见同选组合（环境/检测站 + 数据记录类），默认脚互相不撞**；重叠对写入 `test_pin_bindings` 刻意重叠表。
- **wordlist**：感知传感器组补录 ads1115/tcs34725/mlx90614；新分类「存储/数据记录」补录 at24c02；全部 `lib_modules` 挂接；models 加词条。

### 各件决策

| slug | 手册 | 外设形态 | 母版 syscfg 实例 | 关键决策 |
|---|---|---|---|---|
| `ads1115` | sensor--ads1115-multichannel-a-to-d-sensor.md | 软 I2C 位操作（2 GPIO，照 AHT10 先例，不占硬件 I2C 外设） | 新 GPIO 实例 `ADS1115`/SCL+SDA（SCL 输出 / SDA 双向运行时切换） | API = `ads1115_init`（写默认配置 0xC283：A0 单端 MUX=0x04、PGA=±4.096V(0x01)、连续转换、128SPS、比较器关）+ `ads1115_read(ch)`（**16bit 有符号原始值**，ch 0-3 自动改 MUX 位（AIN0=0x04+ch）→ 写配置 → 读 CONV 寄存器，页面 do-while 重试 ≤20×1ms 保留）+ `ads1115_read_voltage(ch)`（原始/32768×FSR 浮点换算——**页面 `(65535-num)*0.000125` 负数分支与 `num>32768`（未含 32768）系上游缺陷，改 int16_t 正确换算，notes 记录；页面 `0.000125=4.096/2^15` 分辨率式正确）+ 配置服务函数 `ads1115_write_config(cfg)`/`ads1115_set_gain(idx)`（FSR 6.144V~0.256V 六档）/`ads1115_set_data_rate(idx)`（8~860SPS 八档）/`ads1115_set_address(addr7)`（A0/A1 可选，默认 0x48<<1=0x90 保留页面原式）；**与库内 adc（板载 12bit，ADC12_0 MEM0 单通道轮询）分工写入 notes**：adc = 板载单通道（默认 PA24，us016 共享同槽），ads1115 = I2C 外扩 4 通道 16bit（MUX 任选 AIN0-3），多路模拟量/分离供电场景用 ads1115，单路板载用 adc——两件同选互不冲突（不同总线/引脚）；默认 SCL=PA16/SDA=PA17——与 DC_MOTOR 编码器 AA/AB + RC522 MOSI/MISO 重叠（外扩多通道 ADC 与双电机闭环车/读卡门禁同选概率最低） |
| `tcs34725` | sensor--tcs34725-color-recognition-sensor.md | 软 I2C 位操作（2 GPIO，同先例） | 新 GPIO 实例 `TCS34725`/SCL+SDA | API = `tcs34725_init`（读 ID 寄存器判 0x44(TCS34725)/0x4D(TCS34727)，成功设 24ms 积分（INTEGRATIONTIME_24MS 保留页面）+ 1X 增益 + Enable（0x03 两段写，页面 `if(id==0x4D \| id==0x44)` 按位或写法改 `\|\|`——语义等价写法修正）+ `tcs34725_read_rgb(&rgbc)`（STATUS AVALID 判定，出参 c/r/g/b 16bit——页面 GetRawData 语义；「读两次读到的颜色总是上一次」系页面演示循环注记，本实现按 STATUS 判定）+ `tcs34725_rgb_to_hsl(&rgbc,&hsl)`（**页面 RGBtoHSL 保留原式**，HSL 出参；`max3v/min3v` 宏保留）+ 配置服务 `tcs34725_set_integration_time/set_gain/enable/disable` + 底层 `tcs34725_write_reg/read_reg`（COMMAND_BIT 0x80 + 地址 0x29<<1=0x52 按页面）；全局 `rgb/hsl` 收敛为出参；默认 SCL=PA23/SDA=PA24——与 HUIDU L2/L3 + DEBUG/UWB/HC05 UART（PA23/PA24）+ NRF CSN/CE + ADC12_0 MEM0(adc+us016) 重叠（颜色识别与无线链路/巡线/板载 ADC 同选概率最低——颜色识别属视觉类，与 K230 视觉互替；刻意不叠 OLED PB2/PB3/MAX7219 显示件——显示颜色值是常见搭配） |
| `mlx90614` | sensor--mlx90614-non-contact-temp-sensor.md | 软 I2C（SMBus 兼容）位操作（2 GPIO，同先例） | 新 GPIO 实例 `MLX90614`/SCL+SDA | API = `mlx90614_init`（SMBus 无初始化序列——空实现占位保持 API 一致，注释说明）+ `mlx90614_read_object_temp(float *temp_c)`（RegAddr 0x07）+ `mlx90614_read_ambient_temp(float *temp_c)`（RegAddr 0x06）——0.01℃ 级分辨率（页面 `raw*0.02-273.15` 换算保留，**出参换算按页面 0.02 系数**）+ 底层 `mlx90614_read_word(reg, &raw)`（读 2 字节低 8 位在前，ACK/NACK 按页面）；失败返回 0/1 **不返回 0.0 语义不明值**（页面 `return 0.0` 与合法 0℃ 冲突，改出参+状态，notes 记录）；器件地址 `MLX90614_ADDR 0x5A`，读写位 `(0x5A<<1)|0/1` 按页面原式；**notes 写明 SMBus 时序差异与页面实现取证**：① 页面 PEC_Calculation（CRC-8 多项式 X8+X2+X1+1）整段注释未启用 → 剔除，本实现不含 PEC（MLX90614 读无 PEC 校验也能通，页面演示即如此）；② 命令字节 = BIT7~5(RAM/EEPROM 选择) + BIT4~0(地址)，页面 RegAddr 直传 0x06/0x07（Ta/To）即此构造；③ 页面函数注释名 `MLX90615_Read` 与函数名/器件不符 → 按 MLX90614 命名；④ 读时序无额外 `delay_ms(1)`（页面已注释掉），保持逐字节 ACK/NACK；默认 SCL=PA9/SDA=PA8——与 DIGIT_UART RX/TX（K230 视觉串口）、IR_BEAM OUT、HC05 STATE、JOYSTICK SW、NRF24L01 MISO 重叠（非接触测温与视觉（K230 互替类）/手动输入/蓝牙/2.4G 链路同选概率最低；刻意不叠温湿度/光照/显示件——测温与传感站/显示为常见搭配；不叠硬件 I2C I2C_0 脚——软 I2C×硬件 I2C 同脚为物理冲突分组） |
| `at24c02` | control--at24c02-eeprom-memory.md | 软 I2C 位操作（2 GPIO，同先例） | 新 GPIO 实例 `AT24C02`/SCL+SDA | API = `at24c02_init`（I2C 存储无初始化——空实现占位，注释说明）+ `at24c02_write_byte(addr, data)` + `at24c02_read_byte(addr)`（**页面原式**：伪写定位 + 重 start + 读地址 0xA1 读 1 字节 NACK）+ `at24c02_wait_write_done()`（**写周期等待封装**：delay_ms(AT24C02_WRITE_CYCLE_MS=5)，页面演示 `delay_ms(5)` 后读 + 页写 `at24c02_write_page(addr, data, len)`（16 字节页缓冲，跨页边界/len>16 拒收——页面正文「地址计数器自动翻转、先前数据被覆盖」防患，页面无代码按正文实现，notes 记录）+ `at24c02_read_block(addr, buf, len)`（连续读，页面正文「连续读」描述实现，last 字节 NACK）；**地址宏纠正**：页面 `AT24C02_ADDRESS_READ 0xA0`/`AT24C02_ADDRESS_WRITE 0xA1` 宏名与语义**颠倒**（0xA0=写 0xA1=读，页面正文与注释「SLAVE ADDRESS+W为0xA0」印证）——本实现 `AT24C02_ADDR_WRITE 0xA0`/`AT24C02_ADDR_READ 0xA1` 纠正命名，notes 记录上游缺陷；默认 SCL=PB24/SDA=PB8——与 STEP_MOTOR RST2/DCY2 + SR04 TRIG/ECHO + HC05 KEY 重叠（EEPROM 存储记录与步进/测距同选概率最低——记录类与运动类不同框，记录+传感站类同选时与同批默认不撞） |

### 默认脚与重叠全景（2026-09-06 定稿）

四件默认脚 = **PA16/PA17（ads1115）、PA23/PA24（tcs34725）、PA9/PA8（mlx90614）、PB24/PB8（at24c02）**——全部与既有默认重叠、四件互不相撞（环境/检测站 + 数据记录 = 最常见同选组合，默认即不撞）；与既有软 I2C 先例（aht10/pca9685=PB6/PB7、bh1750=PA12/PA13、dht11=PB7）亦不撞。

- 与既有默认重叠计数（更新 test_pin_bindings.py 刻意重叠表）：PA16 2→3、PA17 2→3、PA23 5→6、PA24 5→6、PA9 3→4、PA8 3→4、PB24 3→4、PB8 2→3。
- mlx90614 默认脚选型备注：不叠硬件 I2C I2C_0 的 PA0/PA1（软 I2C GPIO × 硬件 I2C 外设同脚 = 共享分组的物理冲突类，且与既有 i2c_bus_share 测试互扰——2026-09-06 实测调整）；不叠温湿度/光照/显示件（测温与传感站/显示为常见搭配）。
- 四件均为软 I2C 位操作（不占硬件 I2C 外设），同 I2C 总线（SCL/SDA 同脚）多器件挂载属合法总线共享——但因默认脚已按「同选不撞」分配，同选多件时各占一组 GPIO（软件多总线），无需绑定消解；若用户希望多件共享同一组软 I2C 总线，经引脚绑到同一对脚即可（软件 I2C 总线共享合法性与 AHT10/PCA9685 同款——notes 说明）。

### 网盘依赖（本批无）

本批四件页内源码完整（v7 审计通过）。例外项随 notes 记录、不阻塞：全部未上板（软 I2C 时序/MUX 切换/页写周期真机验证留后续）；tcs34725 页面提供两个网盘链接（资料+代码）均随 notes 记录。

## 测试决策

照批次 1-4 先例逐件：

- `tests/test_pins.py::MSPM0_DEFAULT_MAP` 增映射 8 条（四件 × SCL/SDA，均 GPIO 组实例定位）；
- `tests/test_pin_bindings.py` 刻意重叠表更新（PA16/PA17/PA23/PA24/PA0/PA1/PB24/PB8 计数与注释）；
- `tests/test_syscfg_prune.py` 增 ADS1115/TCS34725/MLX90614/AT24C02 实例保留/裁剪断言；
- 新增 `tests/test_module_ads1115.py` / `test_module_tcs34725.py` / `test_module_mlx90614.py` / `test_module_at24c02.py`：manifest 结构（仅 mspm0、依赖 delay、双角色 = gpio_out 默认集）+ mspm0 单选生成（syscfg 含实例 + 模块文件落盘 + main.c 调 init/服务函数过静态门禁）；
- **关键源码守卫**（防公式/时序走样，ir_remote_tx `burst_cycle_formula_guard` 先例）：
  - ads1115：0x70 地址改写（MUX 位掩码/通道编码）、`/ 32768.0f` 电压公式守卫；
  - tcs34725：`|| id == 0x44` 判定守卫、RGBtoHSL 公式文本守卫（max3v/min3v 保留）；
  - mlx90614：`* 0.02f - 273.15f` 换算守卫、RegAddr 0x06/0x07 常量守卫；
  - at24c02：0xA0/0xA1 宏名纠正守卫、5ms 写周期常量守卫。
- 编译级验收：复制 `run_fingerprint_matrix.py` 改 slug，gmake 真编译（`C:/ti/ccs2050`）0 error 硬门槛、模块自身 warning 0；结果回写 manifest verified/notes。

## 范围外

- 其余传感器/控制件（气体/气压/触摸/微波雷达/指纹图像上传、彩屏 6 件 + 0.96 SPI 单色需网盘——批次 7 先例）另立工单。
- stm32 平台条目、上板真机验证（真机留后续，notes 注明）、新 ADC/TIMER/硬件 I2C 外设实例（本批全部 GPIO 实例）。
- 正文内嵌段落（行拆散版）不作为提炼源。
- ADS1115 比较器模式（Lo_thresh/Hi_thresh 寄存器、ALERT/RDY 引脚）——页面明确「用不到」，不实现（notes 说明）。
- TCS34725 中断（AINT/阈值寄存器族）——页面未用中断路径（Enable 只 PON|AEN），不实现（notes 说明）。
- AT24C02 写保护（WP 脚）——模块板级引脚，驱动不管理（notes 说明）。

## 补充说明

- 排序依据：批次 1-4 决策记录延续——本批按 I2C 增强件常用度排序：ads1115（先做打样）→ tcs34725 → mlx90614 → at24c02。
- 审计脚本 `.scratch/wiki-materials/audit_v7.py` 可复跑；本批四件均在 v7 全自洽清单内（真缺 12 篇名单中无本批四件）。
- 工单：`issues/01-module-ads1115.md` → 02 tcs34725 → 03 mlx90614 → 04 at24c02（互相独立，可并行；实施按简→繁）。
- 完成后：全量测试套件 + 批次 1+2+3+4+5 全部 19 件 code-review 收尾 + CONTEXT.md 平台行补录 + 中文提交（.githooks/commit-msg 强制中文；.ps1 若新增按 UTF-8 with BOM 存）。
