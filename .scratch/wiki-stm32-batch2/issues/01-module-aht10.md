# 01 — aht10 温湿度传感器（软 I2C 总线件，手册 sensor--aht10-temp-humi-sensor.md）

**要做什么：** 模块库 `aht10` 新增 **stm32 平台条目**（mspm0 条目零改动）：从地阔星页面「代码块」提炼 AHT10 温湿度驱动为纯驱动切片（软 I2C 位操作：2 GPIO + SDA 方向运行时切换，不占硬件 I2C 外设/TIMER），API 与 mspm0 版完全对齐——`aht10_init()`（50ms 稳定 + 校准 0xE1 0x08 0x00）、`aht10_read(float *t, float *h)`（0x70 写 → 0xAC 0x33 0x00 触发测量 → 20ms+≤5×1ms 读地址重试 → 6 字节回包：状态+湿度 20bit+温度 20bit；0=成功/1=超时）、`aht10_read_temperature()/aht10_read_humidity()`（便捷封装）。选中 stm32 生成工程打开即可编译、可调用，不再「需自备」。

**关键事实（已取证，开工前已读原页，行号以 md 文件为准——sources/materials/lckfb-地阔星移植手册/sensor--aht10-temp-humi-sensor.md）：**
- 页面 = **F1 标准库**（`stm32f10x.h` + `RCC_APB2PeriphClockCmd(RCC_AHT10)` + `GPIO_Mode_Out_OD` + `GPIO_Mode_IPU` + `GPIO_Mode_Speed_50MHz`——非 F4 嫌疑页）。
- 模块来源（页面「一、模块来源」）：采购 `https://item.taobao.com/item.htm?spm=a230r.1.14.28.5b982786BAvoXy&id=630894804483&ns=1&abbucket=19#detail`（AHT10 高精度数字型温湿度传感器测量模块 I2C通讯 代替sht20）；网盘 `https://pan.baidu.com/s/1xTX_QCmEmy8DWgxgtgXXFw`（提取码 pp3k）+ 移植成功案例 `https://pan.baidu.com/s/1d2-sh5rv6i65tjaobgpnfg?pwd=r99d`（提取码 r99d）。
- 规格（页面「二、规格参数」）：1.8~3.6V、0.25~23uA、湿度 ±2%RH、温度 ±0.3℃、IIC、3 Pin。
- 代码块结构：块 1 = 移植说明（地址 0x38 → 0x38<<1 = 0x70；采集步骤逐字节 + 状态字示例 0x1C）；块 2 = bsp_aht10.c（L79-403：IIC_Start/Stop/Send_Ack/I2C_WaitAck/Send_Byte/Read_Byte/AHT10Reset/AHT10_GPIO_Init/AHT10_Read/Get_Temperature/Get_Humidity + 全局 `float Temperature/Humidity`）；块 3 = bsp_aht10.h（L407-460：RCC_AHT10=RCC_APB2Periph_GPIOB、PORT_AHT10=GPIOB、GPIO_SDA=GPIO_Pin_9、GPIO_SCL=GPIO_Pin_8、SDA_OUT（）=GPIO_Mode_Out_OD、SDA_IN（）=GPIO_Mode_IPU、SDA_GET=GPIO_ReadInputDataBit、SDA(x)/SCL(x)=GPIO_WriteBit）；块 4 = main 演示（L466-509：board_init+uart1_init(115200)+`AHT10_GPIO_Init()`+while(1){AHT10_Read();printf 温度/湿度;delay_ms(1000)}——整体剔除）。
- **页面默认脚 = PB8（SCL）/PB9（SDA）**——**恰好 = 母版 OLED_GPIO 段（PB8/PB9）！** OLED 与环境站同框概率极高（温湿度+显示=标配组合），不照抄（见引脚与默认脚）。
- 页面读地址 0x71 = `0x38<<1 | 1`；写地址 0x70 = `0x38<<1 | 0`（页面 0X70/0X38<<1 混用但值一致——原式保留 0x70/0x38<<1 注释）。
- **页面缺陷清单（已取证，全部 notes+守卫）**：
  1. **每读后重复复位+初始化**（AHT10_Read L372-373 调 `AHT10Reset()+AHT10_GPIO_Init()`——每次读取多 ~100ms（2×50ms 稳定延时）+ 读后即复位器件；页面 AHT10Reset=0xBA 软复位、GPIO_Init=0xE1 0x08 0x00 校准，两序列并存自洽但读后全做一遍 = 冗余）→ 合并进 init（mspm0 版已同——`AHT10Reset + AHT10_Init 检查合并进 init`）。
  2. **AHT10_GPIO_Init 内 Send_Byte 连发无应答检查**（L297-303：0x70/0xE1/0x08/0x00 之后直接 IIC_Stop——无 I2C_WaitAck；AHT10Reset L270-275 亦无）→ init 补 wait_ack（照 Read 段正确做法，mspm0 版已同）。
  3. **读地址重试超时后不判失败**（L335-340 do-while 后无 `timeout` 检查——超时无应答仍继续 Read_Byte 读垃圾数据）→ `if (timeout >= 5) return 1`（mspm0 版已同；页面返回 0 恒成功语义修正）。
  4. **注释与值矛盾**：L339 `Send_Byte(0X38<<1 | 1);//器件地址+写命令`——0x38<<1|1 = **读**地址，注释应为「器件地址+读」。
  5. 类型宽度/冗余：L317 `char timeout`（有符号）→ uint8_t；L174 `char ack` 只声明未读入（成功路径恒返回 0——语义正确，变量冗余）→ 删除冗余变量。
  6. I2C_WaitAck 成功路径 L199-201 `SCL(0); SDA_OUT();` 后 `SDA(0)`（应答后把 SDA 拉低 = 页面原式——保留，mspm0 版同）。
- mspm0 版对照（对齐目标）：aht10.c/.h 见库内（init/read/read_temperature/read_humidity、0x70 原式、20ms+5×1ms 重试、湿度=b1..b3 高 4 位/温度=b3 低 4 位+b4..b5、dat/1048576 换算、返回 0/1）。

**换算实现**（ml_* 母版 API，零寄存器级字面量）：
- 引脚初始化：`gpio_init(AHT10_SCL_GPIO, AHT10_SCL_PIN, OUT_OD)` + `gpio_init(AHT10_SDA_GPIO, AHT10_SDA_PIN, OUT_OD)`（页面 GPIO_Mode_Out_OD 原式；时钟使能在 gpio_init 内部）——**不用母版 ml_i2c**（零延时裸跑 72MHz + 引脚硬绑 PA11/PA12 USB 共用脚——spec 决策①）。
- 原语族（照 mspm0 版结构 + 页面原式）：`AHT10_SDA_OUT() = gpio_init(SDA, OUT_OD)`、`AHT10_SDA_IN() = gpio_init(SDA, IU)`（页面 GPIO_Mode_IPU→IU）、`AHT10_SDA(x)/AHT10_SCL(x) = gpio_set(...)`、`AHT10_SDA_GET() = gpio_get(...)`；`aht10_iic_start/stop/send_ack/wait_ack/send_byte/read_byte`（时序 = 页面原值：start 4us/4us、send_byte 1/2/2、wait_ack 1/1/2+3×10 次、read_byte 2/2/1、send_ack 2/2——≈100kHz 级，AHT10 ≤400kHz 裕量足）。
- `aht10_init`：`delay_ms(50)` → start → 0x70 → wait_ack → 0xE1 → wait_ack → 0x08 → wait_ack → 0x00 → wait_ack → stop → `delay_ms(50)`（页面校准序列 + 补应答检查——缺陷②修正；页面 AHT10Reset 0xBA 软复位不单设（缺陷①修正——复位不重复做，真机冷启动自复位状态由 0xE1 校准语句覆盖）。
- `aht10_read`：start → 0x70 → wait_ack（页面不检查写段应答——保留页面对 mspm0 版同构）→ 0xAC/0x33/0x00 → stop → `delay_ms(20)`（页面 L362 原值）→ ≤5×（1ms + start + 0x71 读地址重试）→ 超时 `return 1`（缺陷③修正）→ 6 字节（末字节非应答）→ 换算（湿度 = ((b1<<12)|(b2<<4)|(b3>>4))/1048576×100；温度 = (((b3&0x0F)<<16)|(b4<<8)|b5)/1048576×200−50——页面原式，b3 高位湿度/低位温度切分正确）→ `return 0`。
- 全局 `Temperature/Humidity` → static 收敛 + 出参（read 带双指针、NULL 容错；read_temperature/read_humidity 便捷封装内部完成一次读取）。

**引脚与默认脚（同选概率最低推理——六件共总线）：**
- pins：`AHT10_SCL`（type `i2c_scl`，default **PA6**，required true，macros `[AHT10_SCL_GPIO, AHT10_SCL_PIN]`）、`AHT10_SDA`（type `i2c_sda`，default **PA7**，required true，macros `[AHT10_SDA_GPIO, AHT10_SDA_PIN]`）。
- pin_config.h 新宏段：`#define AHT10_SCL_GPIO GPIO_A / AHT10_SCL_PIN Pin_6 / AHT10_SDA_GPIO GPIO_A / AHT10_SDA_PIN Pin_7`（注释：默认 PA6/PA7 = 叠 `MOTOR_A_DIR/DIR2`（TB6612 A 相方向）——环境传感与「带电机方向的小车运动控制」不同框、同选概率最低；**六件（aht10/bh1750/sht20/sht30/at24c02/ags10）默认共挂此总线**（器件地址 0x38/0x23/0x40/0x44/0x50/0x1A 全异、多挂协议允许 = 合法共享）；与既有 `I2C_GPIO`（PA11/12，USB 共用脚——**不用**：页面原式=母版 OLED 段 PB8/9 亦不用（OLED 同框极高））、`OLED_GPIO`（PB8/9）零重叠；同选时经引脚绑定消解（逐脚端口宏，换脚零组约束））。
- 设计依据：刻意不叠显示/声光/输入/串口/无线（OLED PB8/9、LED PC13-15、BUZZER PA15、KEY PB3、DIP/GRAY/TTP224 PB12-15/PB3/PB6/PB7/PA8、DEBUG PA2/3、UART1 PA9/10、ZIGBEE PB10/11、USB PA11/12、SWD PA13/14）——PA6/7 是「电机方向」专属（车题组件），与传感站类不同框概率最低。

**被谁阻塞：** 无——可立即开始（本批打样件）。

**状态：** resolved

**实施清单：**
- [x] `library/modules/aht10/code/aht10_stm32.c/.h`（UTF-8；.h 含 <stdint.h>；.c include 本模块 .h + `pin_config.h` + `headfile.h`；零引脚字面量；时序/换算/修正注释保留；页面原式 0x70 注释保留；SDA 方向切换 = gpio_init 重配 OD/IU；**出参判空用 0 非 NULL**——F1 头无 NULL，UV4 首编 2 error 修正记录）
- [x] `manifest.json` platforms 增 stm32：files `[code/aht10_stm32.c, code/aht10_stm32.h]`、verified false（矩阵过转 **true**）、hardware_bound false、pins 如上（type i2c_scl/i2c_sda）、kit（页面「模块来源」AHT10 高精度数字型温湿度传感器测量模块 I2C通讯 代替sht20）、source_url `https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/aht10-temp-humi-sensor.html`、notes（手册路径 `sources/materials/lckfb-地阔星移植手册/sensor--aht10-temp-humi-sensor.md` + 原页 + 网盘×2+提取码（资料 pp3k / 成功案例 r99d）+ 采购 + **页面缺陷清单 6 条**（每读后重复复位初始化/init 无应答检查/超时不判失败/注释地址与值矛盾×3（L339 读地址注释/L358 ack 注释/L298 获取状态注释）/类型宽度 char→uint8_t + 已知规格偏差 5×1ms+20ms ≪ 80ms）+ 换算要点（F1→ml_*、OD/IU 页面原式、时序 2-4us ≈100kHz）+ 默认脚推理（页面默认 PB8/PB9=OLED 段不照抄）+ 与 mspm0 分工 + 未上板）
- [x] `library/masters/stm32/pin_config.h` 增 `AHT10_SCL_GPIO/AHT10_SCL_PIN/AHT10_SDA_GPIO/AHT10_SDA_PIN` 宏段 + **六件全量宏段**（aht10/bh1750/sht20/sht30/at24c02/ags10 ×4 = 24 宏一次落位——共总线同值，注释含批次 2 推理）
- [x] 测试 `tests/test_module_aht10.py`：形状（stm32 条目/files/pins 元组/kit+source_url/notes 子串）+ mspm0 零改动守卫 + stm32 单选生成全流程（uvprojx 注册 aht10_stm32.c + pin_config.h 在工程根）+ 守卫（无 printf/main/GPIO_Init/RCC_/stm32*.h/ml_i2c/GPIO_ReadInputDataBit/GPIO_WriteBit；0x70/0x38<<1 原式注释；0xE1 0x08 0x00 校准；`timeout >= 5` 超时返回（缺陷③防回潮）；换算原式 `1048576.0f`；无 `AHT10Reset` 调用残留（缺陷①防回潮））
- [x] `tests/test_pins.py` STM32_MACRO_VALUES 补 AHT10 4 宏（GPIO_A/Pin_6/GPIO_A/Pin_7 注释批次 2）；`tests/test_default_layout.py` 白名单 PA6/PA7 组（aht10 SCL/SDA + motor MOTOR_A_DIR/DIR2——六件入组随各工单逐个扩展，注释总线共享/批次 2）
- [x] 编译矩阵：`.scratch/wiki-stm32-batch2/matrix/run_aht10_matrix.py`（照 run_relay_matrix.py；MAIN_C 调 aht10_init + aht10_read(&t,&h) + read_temperature + read_humidity (void) 化）→ UV4 `-j0 -r -b` **exit 0，0 error、0 module warning** → verified=true + notes 回写
- [x] 中文提交 → resolved → 结论回填

**验收记录：**
- 矩阵 PASS：UV4 V5.06u7 `-j0 -r -b` exit 0，`0 Error(s), 0 Warning(s)`；编译日志 `.scratch/wiki-stm32-batch2/matrix/aht10/build.log`；产物 Program Size: Code=3556（浮点软库路径）。
- 首编修复记录：`identifier "NULL" is undefined`（aht10_stm32.c L187/191）——F1 标准库头无 NULL 定义（TI 头有）→ 出参判空改用 `!= 0`（mspm0 版 NULL 保留零改动，平台差异 notes）。
- 换算/原语要点回填：页面 GPIO_Mode_Out_OD+IPU 原式 → ml_gpio OUT_OD/IU（与 mspm0 版推挽/浮空语义等价，均需总线外上拉——页面真机验证过）；IIC 原语族 → aht10_iic_* 静态（页面非 static 外链——跨页撞名共性已消）；全局 Temperature/Humidity → static 收敛 + 出参；ACK 单参化（页面 ack=0 应答/1 非应答，末字节 send_ack(1) 注释已纠）。
- 页面缺陷回填（全部 notes + 守卫）：① 每读后重复复位+初始化（AHT10Reset 0xBA 软复位 + 0xE1 0x08 0x00 校准——读后全做一遍 ~100ms 冗余）→ 合并进 init；② init 连发无应答检查 → 补 wait_ack；③ 读地址重试超时后不判失败（照抄读垃圾）→ timeout>=5 return 1；④ L339 注释「写命令」实为读地址（+ L358 ack 注释 / L298 获取状态注释——三处注释与行为不符）；⑤ char timeout → uint8_t、char ack 死变量删；**已知偏差**：窗口 20ms+5×1ms ≪ 手册 ≥80ms（按页面/mspm0 原式保留，真机失败单点调大读前延时，notes 记录）。
- 测试：test_module_aht10 7 passed（双平台形状 + 宏存在 + stm32/mspm0 单选生成 + 代码守卫）；test_pins/test_default_layout 26 passed 组合跑。
- 词表：aht10 已挂接（mspm0 批），零补录；依赖 ["delay"] 模块级已有，零改动。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
