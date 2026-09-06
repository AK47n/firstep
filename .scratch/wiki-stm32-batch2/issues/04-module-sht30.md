# 04 — sht30 温湿度传感器（软 I2C 总线件 + CRC8，手册 sensor--sht30-temp-humi-sensor.md）

**要做什么：** 模块库 `sht30` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面「代码块」提炼 SHT30 温湿度驱动为纯驱动切片（软 I2C：2 GPIO + SDA 方向切换；周期测量模式 0x2130），API 与 mspm0 版完全对齐——`sht30_init()`（0x2130 周期模式每秒 1 次高重复）+ `sht30_read(float *t, float *h)`（0xE000 读命令 → 读地址应答重试 ≤20×2ms → 6B（温度高/低+CRC+湿度高/低+CRC）→ CRC8（0x31/0xFF）双组校验 → 温度 = data/65535×175−45、湿度 = data/65535×100；0=成功/1-5=页面失败码）+ `sht30_read_temperature/humidity`（便捷封装）。

**关键事实（已取证，开工前已读原页，行号以 md 文件为准——sensor--sht30-temp-humi-sensor.md；详见 %TEMP%\batch2-facts.md 第 4 节）：**
- 页面 = **F1 标准库**（stm32f10x.h + RCC_APB2PeriphClockCmd；**SDA_OUT=GPIO_Mode_Out_PP、SDA_IN=GPIO_Mode_IN_FLOATING——全批唯一推挽+浮空配置**，其余 5 页为 OD+IPU——记录差异，非矛盾，工作前提=模块自带 1k-10k 上拉）。来源：采购 `https://item.taobao.com/item.htm?spm=a1z09.2.0.0.204e2e8d2hPeAl&id=556043263770&_u=h2t4uge5cf4f`（GY-SHT31-D 数字温湿度传感器模块——采购标题 GY-SHT31-D vs 页面标题 SHT30，同系列记录不裁决）+ 资料 `https://pan.baidu.com/s/1kisMJspcV6Qdr1ye9ElOlQ`（未给提取码）+ 成功案例 `https://pan.baidu.com/s/1kirHyxtW1Oy7B0P63iiXsg?pwd=04r1`。
- 规格：2.4-5.5V、0.2-1500uA、温度 -40~125℃/±0.3℃、湿度 0~100%RH/±2%RH、4 Pin；地址 ADDR 接 VSS = 0x44（实际 0x44<<1）；单次/周期两种模式；**「每个数据值后面总是跟着一个CRC校验和」**；周期模式 0.5-10 次/秒（最快 1 秒 10 次）；读命令 0xE000（读后寄存器清零）；「测量频率过高会导致自热」。
- 代码块：bsp_sht30.c（L72-405：全局 `double Temperature/Humidity` L89/SHT30_GPIO_Init L99（Out_PP 无 SetBits）/IIC_Start L119（**SCL(1)→SDA(0)→SDA(1)→5us→SDA(0)→5us→SCL(0)——多余 Stop→Start 边沿，最终态正确**——mspm0 版逐字保留）/IIC_Stop L140/IIC_Send_Ack L161/I2C_WaitAck L183/Send_Byte L220（**签名用 u8——页面 .h `#define u8 unsigned char`**）/Read_Byte L246/SHT31_Write_mode L280（0x44<<1|0 → 命令高低 8 位，每步检查答返回 1/2/3；**L296 IIC_Stop() 被注释掉——跟手重复起始**）/crc8 L308（0x31/0xFF）/SHT30_Read L336（先 SHT31_Write_mode(0x2130) L343 → 0xE000 写段 → 读地址重试 i>20 return 4 + delay_ms(2) → 6B+CRC → 双组校验 → 换算 → return 0/5；**L402 校验失败 printf**））；bsp_sht30.h（L410-461：**L427 `extern double Temperature, Humidity;` 页外 extern 全局泄漏——全批唯一**、`#define u8 unsigned char` L429、RCC_SHT30=GPIOB、PORT=GPIOB、**GPIO_SDA=Pin_8/GPIO_SCL=Pin_9（页面默认 SDA=PB8/SCL=PB9）**）；main（L485-506：SHT30_GPIO_Init → while(1){SHT30_Read(0xe000) → printf Temp/Humi;delay_ms(1000)}）。
- **页面缺陷清单（全部 notes+守卫）**：① **L44 首句「ADS1115是采用的IIC通信」串台**（ADS1115 页文案残留——模块原理图段内容为空）；② **extern double Temperature/Humidity 页外泄漏**（.h L427——全批唯一，mspm0 已收敛 float 出参）；③ **命令表 0x2126 vs 代码 0x2130 不一致**（注释表 1 次/s = 0x2126（中重复）、代码 0x2130（高重复）——两值皆合法（手册），采信代码，notes 记录）；④ crc8 为通用名 + 非 static（撞名面）+ `#define u8` 全局命名空间污染 → 静态化 + uint8_t；⑤ char ack 死变量；⑥ IIC_Start 多余 Stop→Start 边沿（页面原样——mspm0 同款保留，功能正确）。
- 原语时序：5us 半周期（≈100kHz，SHT30 ≤400kHz 裕量足——页面原值 mspm0 保留）；wait_ack 10×5us。
- mspm0 版（对齐目标）：sht30.c/.h 见库内（init/read/read_temperature/read_humidity；SHT30_ADDR 0x44/CMD_PERIODIC 0x2130/CMD_READ 0xE000/RETRY 20×2ms；CRC8 双组 0x31/0xFF；换算 175/45/100，0.01 系数；失败码 1-5；页面「SHT31_Write_mode 注释掉 IIC_Stop（重复起始）按页面原样不补 STOP」）。

**换算实现**：引脚 gpio_init(OUT_PP)（页面原式推挽——全批唯一）+ SDA 方向切换 gpio_init(SDA, OUT_PP/IF)（页面原式推挽+浮空）；原语族 sht30_iic_*（5us 半周期；时序 = 页面原值）；sht30_write_mode 静态（0x88 → 命令高/低 → 应答检查 1/2/3；**不补 STOP——页面注释掉、跟手重发 START = 重复起始**）；sht30_crc8 静态（0x31 多项式/0xFF 初值）；API = sht30_init（write_mode(0x2130)）+ sht30_read（页面失败码 1-5；出参判空用 0）+ read_temperature/read_humidity（便捷封装，失败返回码 + 出参保持原值）；零寄存器级/标准库调用（校验失败 printf 剔除）、零 ml_i2c。

**引脚与默认脚（同选概率最低推理——六件共总线）：**
- pins：`SHT30_SCL`（i2c_scl，default **PA6**，macros `[SHT30_SCL_GPIO, SHT30_SCL_PIN]`）、`SHT30_SDA`（i2c_sda，default **PA7**，macros `[SHT30_SDA_GPIO, SHT30_SDA_PIN]`）。
- pin_config.h 宏段（已随工单 01 落位）：SHT30_SCL_GPIO=GPIO_A/SHT30_SCL_PIN=Pin_6/SHT30_SDA_GPIO=GPIO_A/SHT30_SDA_PIN=Pin_7。
- 默认脚推理：温湿度与光照/气体/EEPROM 共挂 PA6/PA7（地址 0x44 与其它五件全异——环境站合法共挂；与 aht10/sht20 为互替件——各自默认脚相同（共总线）仍合法：同选时地址不同互不干扰）；与 motor MOTOR_A_DIR/DIR2（电机方向）重叠：温湿度与「带电机方向的小车运动控制」不同框、同选概率最低；**页面默认 SDA=PB8/SCL=PB9 不采用**（= 母版 OLED 段）；同选经引脚绑定消解。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/sht30/code/sht30_stm32.c/.h`（照 aht10_stm32 样式；**PP/IF 页面原式**（全批唯一推挽+浮空）+ 5us 时序 + CRC8 0x31/0xFF 双组 + 失败码 1-5 + NULL→0；页面缺陷注释全记录——ADS1115 串台/extern 泄漏/0x2126 vs 0x2130/u8 宏/char 死变量/多余 Stop 边沿；sht30_crc8/write_mode 静态化）
- [x] `manifest.json` platforms 增 stm32（files/verified false→**true**（矩阵后）/pins 如上/kit=GY-SHT31-D（ADDR 接地 0x44）/source_url wiki 原页/notes 手册路径+原页+网盘×2+采购+缺陷清单+默认脚推理+未上板+矩阵记录）
- [x] 测试 `tests/test_module_sht30.py`（照模板：形状 + 宏存在 + stm32 单选生成 + mspm0 零改动 + 守卫（CRC8 0x31/0xFF/0x2130/0xE000/RETRY 20×2ms/失败码 1-5/换算 175.0/45.0/100.0/无 printf 残留/无 extern 泄漏/无 u8 宏/无 ml_i2c/标准库）——26 组合跑绿）
- [x] `tests/test_pins.py` STM32_MACRO_VALUES 补 SHT30 4 宏；`tests/test_default_layout.py` 白名单 PA6/PA7 组加入 sht30 两角色
- [x] 编译矩阵 → UV4 **exit 0，0 error、0 module warning** → verified=true 回写
- [x] 中文提交 → resolved → 结论回填

**验收记录：**
- 矩阵 PASS：UV4 V5.06u7 `-j0 -r -b` exit 0，`0 Error(s), 0 Warning(s)`；产物 Program Size: Code=3724。
- 换算要点回填：页面 PP+浮空原式 → ml_gpio OUT_PP/IF（全批唯一一派——工作前提 = 模块自带上拉；与其余 5 页 OD+IPU 记录差异非矛盾）；5us 半周期原值；页面 IIC_Start 多余 Stop→Start 边沿按页面原样保留（最终态正确，mspm0 同款）；SHT31_Write_mode 注释掉 IIC_Stop（跟手重复起始）按页面原样不补 STOP；CRC8 0x31/0xFF 双组校验页面原式；失败码 1-5 页面原样（校验失败页面 printf → 剔除返回 5）。
- 页面缺陷回填（全部 notes + 守卫）：① ADS1115 串台（不落）；② extern double 页外泄漏（全批唯一）→ float 出参 + static 收敛；③ 命令表 0x2126（中重复）vs 代码 0x2130（高重复）——两值皆合法，采信代码；④ crc8 通用名非 static + u8 宏污染 → 静态化 + uint8_t；⑤ char ack 死变量收敛；⑥ 多余 Stop 边沿记录保留。
- 测试：test_module_sht30 7 passed（双平台形状 + 宏存在 + stm32/mspm0 单选生成 + 代码守卫）；test_pins/test_default_layout 26 passed 组合跑。
- 词表：sht30 已挂接（mspm0 批），零补录；依赖 ["delay"] 零改动。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
