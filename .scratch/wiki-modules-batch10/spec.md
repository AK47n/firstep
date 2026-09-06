# 批次 10「杂项收尾第一组（温湿度/姿态/大电流驱动/OpenMV4）」— 立创 wiki 地猛星手册模块批量入库

## 问题陈述

批次 1-9 共 35 件已入库（遥控/通信、传感器常用、显示/执行、语音/身份、I2C 增强件、环境监测/温度补充第一组、气体/空气传感器第一组、环境类第二组、ADC 模拟量薄封装群）。`lckfb-地猛星移植手册/` 剩余页中**杂项收尾第一组**四篇页内自带完整驱动源码（v7 审计自包含——`.scratch/wiki-materials/audit_v7.py` 2026-09-11 复跑确认四篇均在 58 篇全自洽名单内，不在 12 篇真·页外符号名单）：SHT20 温湿度（页面 3 代码块自含 SHT20_Read 全驱动）、JY61P 六轴姿态（IIC 原语 + writeDataJy61p/readDataJy61p/get_angle 全驱动）、L298N 大电流电机驱动（AO_Control 方向+调速）、OpenMV4 摄像头（UART 帧解析 + IRQHandler 全驱动）——模块库仍无对应条目：用户做温湿度/姿态采集、大电流/无编码器驱动、OpenMV 视觉帧解析题时，AI 不知道库里有驱动，只能当"需自备"。

按用户裁决：批次 10 = **杂项收尾第一组**四件——全部页内源码完整（v7 全自洽）、无需网盘。

## 方案

照批次 1-9 已确立管线，每件一个工单：手册「代码块」提炼完整 bsp（正文内嵌段落禁用；open_mv4 页内 Python 模块代码块只作参考素材、不落码）→ 纯驱动切片改造（去 main/printf、API 规范化、ADR 0009 无状态机——识别/流程逻辑归生成骨架）→ 母版 syscfg 新实例 + `syscfg_instances.py` INSTANCE_CONSUMERS 登记 → manifest（dependencies/pins/kit+source_url/notes 含手册路径+原页+网盘链接+改造要点+与库内同类分工）→ wordlist.json 补录（感知传感器 SHT20/JY61P、执行机构 L298N、视觉模块 OpenMV——就近分类，lib_modules 挂接）→ 测试（`test_module_<slug>.py` 照 test_module_joystick.py 模板；test_pins.py::MSPM0_DEFAULT_MAP；test_pin_bindings.py 刻意重叠表；test_syscfg_prune.py；open_mv4 帧解析纯函数单测——伪帧序列→坐标结果，最高既有接缝 = test_k230_artifact.py 的 C 源机械比对/纯函数镜像先例）→ 编译矩阵（复制 `run_joystick_matrix.py` 改 slug：单选生成 → SysConfig CLI → gmake 0 error/0 warning 硬门槛）→ verified 回写 → 中文提交 → 工单 resolved → 逐件 code-review。

## 用户故事

1. 作为做题用户，我选中 `sht20`/`jy61p`/`l298n`/`open_mv4` 后，工具自动分配默认脚，生成工程打开即可编译，可调用 init + 服务函数（温湿度读数/姿态角度/方向+调速/视觉帧解析）。
2. 作为做题用户，我做环境温湿度采集（低功耗单次测量）、平衡车/云台姿态角（器件内卡尔曼融合直接出角度）、大电流重载驱动/双电机无编码器场景、OpenMV 视觉中心坐标解析时，不用再读器件手册。
3. 作为维护者，查看每个新条目能看到平台条目（verified/kit/source_url/网盘链接/改造要点/编译记录/UART 放置决策依据/与库内同侪分工），可溯源到手册。

## 实现决策

### 既定事实（勿重新调研，批次 1-9 已实证）

① ADC12_0 八通道已满（endAdd=7）——本批无 ADC 类（ms1100 留批次 11 薄封装）；② SysConfig 拒绝同一 UART 外设多实例（Resource conflict "UART2 is already in use by ..."；**UART 模块实例上限 = 4** = UART0-3 外设数——批次 4 前置调研 CLI 实证，母版全量布局本身不可 CLI 验证，每工程先裁剪、裁剪后每外设至多一实例（指纹「裁剪后独占」先例））——UART 类新件先读批次 4/01-04 结论取证（本次已读：`.scratch/wiki-modules-batch4/spec.md` UART 可行性调研段 + `04-module-fingerprint.md` 结论）；③ 地猛星 2×20 排针 31 个 IO 全被默认布局占用——新模块默认脚按「与同选概率最低者重叠」，同选经引脚绑定消解；④ **PA0/PA1 不可作 GPIO 输入**（2026-09-06 SysConfig CLI 实证；GPIO 输出可配——ir_remote_tx/gp2y1014au 先例）——软 I2C 的 SDA 需 INPUT（SDA_IN + SDA_GET），故软 I2C 件默认脚不得用 PA0/PA1；⑤ 母版 GPIO 中断全走 GROUP1 单向量且被 motor 编码器独占——本批全部轮询，不注册 GPIO 中断；⑥ 软 I2C 先例 aht10/批次5/sht30/sgp30/ags10（2 GPIO、SDA 方向运行时切换、delay 模块延时不占 TIMER、不占硬件 I2C 外设）、软 SPI 先例 nrf24l01/max7219/rc522、软 UART TX 先例 jq8900/syn6288、忙等不占 TIMER（sr04/ws2812 先例）；⑦ 工具链 `C:/ti/ccs2050`、SysConfig CLI `C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat`；⑧ 页内符号异常/器件正确性缺漏→人工复核、修正并记 notes（ir_remote 反码、sgp30 CRC8、ags10 重试写反、rain 公式方向、microwave PA0 实证先例）；⑨ 一致性快检先例 `.scratch/wiki-modules-batch9/sweep_35_modules.py` → 本批后更新 **39 件版**。

### 共性（四件一致）

- **仅 mspm0 平台条目**（stm32 缺条目 = 生成时 missing 警告，批次 1 先例）；`hardware_bound: false`；`verified` 初始 false，编译矩阵通过转 true；未上板（notes 注明）。
- **代码提炼**：从手册「代码块」章节抽完整 bsp，改造为 `xxx_init()` + 服务函数，去 main/printf，函数名规范化（去 `SHT20_Read`/`get_angle`/`AO_Control`/`Openmv4DataAnalysis` 形态按库风格重命名），全局状态收敛为模块内静态 + 出参；open_mv4 的 Python 侧（OpenMV4 代码块）仅作参考素材——帧格式来源，不落主控代码。
- **软 I2C（sht20/jy61p）**：照 sht30 先例——SCL/SDA 两 GPIO、SDA 方向运行时切换（写=输出、读 ACK/数据=输入）、位操作延时走 delay 模块（半周期 5us ≈ 100kHz 级）、不占硬件 I2C 外设/TIMER；IIC 原语族（start/stop/send_ack/wait_ack/send_byte/read_byte）静态化；**默认脚不得用 PA0/PA1**（既定事实④——SDA 需输入模式）；节点需板上/模块自带上拉。
- **引脚宏参数化**：按 manifest pins 角色 + 母版 syscfg 实例宏名对齐（`<实例>_<引脚>_*` 命名，sht30/aht10 先例；PWM 通道走 `GPIO_<实例>_C0_IDX`、UART 走 `<实例>_INST`——motor/fingerprint 先例）。
- **wordlist**：就近分类补录——SHT20/JY61P 挂「感知传感器」（models + solutions + lib_modules）、L298N 挂「执行机构」（L298N 方案补 lib_modules）、OpenMV 挂「视觉模块」（既有 OpenMV Cam H7 方案补 lib_modules 并更新 note）。

### 各件决策

| slug | 手册 | 外设形态 | 母版 syscfg 实例 | 关键决策 |
|---|---|---|---|---|
| `sht20` | sensor--sht20-temp-humi-sensor.md | **软 I2C**（SCL 输出 + SDA 双向运行时切换） | 新 GPIO 实例 `SHT20`（SCL/SDA 2 associatedPins，均 OUTPUT 初值 CLEARED） | API = `sht20_init`（空实现——SYSCFG_DL_init() 生效；单次测量模式无需预置命令）+ `sht20_read(float *t, float *h)`（0=成功/1=温度段失败/2=湿度段失败——页面 SHT20_Read 单值读改两段合并；各段内部细分码保留于 `sht20_measure_once`：1=写地址应答失败、2=测量命令应答失败、3=读地址应答超时；失败时出参不变——成功出参 ℃ 与 %RH）。**器件正确性修正（人工复核记 notes）**：① 页面 `IIC_Wait_Ack` 超时重试计数 10 次×5us 保留但按 sht30 先例并入服务函数（超时 1=无应答）；② **测量等待按页面**：发测量命令（0xF3 温度/0xF5 湿度——**no-hold 单次测量**，低功耗模式）后重发读地址轮询直到传感器应答——页面最长测量时间 85ms（温度 14bit）/29ms（湿度 12bit），页面 do-while 裸循环改 **≤50×2ms 重试**（100ms 覆盖 85ms 上限，sht30 应答重试先例；页面 delay_us(10) 忙等不保证覆盖，notes 记录）；③ **换算按页面原式**：温度 = raw/65536.0×175.72−46.85、湿度 = raw/65536.0×125−6（0.01 系数口径——页面演示 ×100/%02d 打印，本件直接出 float ℃/%RH）；④ **14bit 数据低 2 位状态位掩码修正**（页面正文「两个状态位在物理计算前须置 0」但代码未掩码——按 SHT2x 手册 `& 0xFFFC` 修正，notes 记录；误差 <0.01℃/0.05%RH）；⑤ **CRC 按页面取舍：无**——页面注释「校验和可以不需要，不需要则在数据接收完后发 NACK」，页面代码即 2 字节 + NACK（无 CRC 字段）；notes 写明 SHT2x 支持 CRC8（0x31/0xFF，sht30 模块原式），需要时按 sht30 先例补。与库内分工 notes：**aht10/dht11 为常用温湿度互替件、sht30 为 I2C 周期模式 0x44 地址件——sht20 是 SHT2x 旧系列（地址 0x40、单次测量低功耗、±0.3℃/±3%RH 精度档），三件同选互不冲突（默认脚各不相同）**；**软 I2C 地址冲突提醒**：多 I2C 模块共总线时需不同地址或共享总线时序——aht10/SHT30/mq2?（无）…库内软 I2C 件（aht10 0x38 / sht30 0x44 / sht20 0x40 / pca9685 0x40 / bh1750 0x23 / tcs34725 0x29 / mlx90614 0x5A / at24c02 0x50 / ads1115 0x48 / sgp30 0x58 / ags10 0x1A）——**sht20 地址 0x40 与 pca9685 地址 0x40 同址**：同总线双选 = 地址冲突（写入互相寻址），同选时须改器件地址（SHT20 地址不可改（SHT2x 固定 0x40）、pca9685 有 A0-A5 跳线——真机上错开或换总线），notes 写明；默认 SCL=**PA16**/SDA=**PA17**——与 DC_MOTOR 编码器 AA/AB（双电机闭环车）、RC522 MOSI/MISO（读卡门禁）、ADS1115 SCL/SDA（外扩多路 ADC）重叠：温湿度与闭环车/读卡/多路模拟采集不同框、同选概率最低（**刻意不叠**温湿度互替件 aht10 PB6/PB7、dht11 PB7、sht30 PA28/PA31、ds18b20 PA7、mlx90614 PA9/PA8 与光照 bh1750 PA12/PA13——温湿度+显示/其他传感为环境站常见搭配，sht30/ds18b20 先例），同选时经引脚绑定消解 |
| `jy61p` | sensor--jy61p-measurement-sensor.md | **软 I2C**（同上；页面 12Pin 模块 IIC 控制方式，默认 9600 串口为备选——本件按页面 IIC 例程） | 新 GPIO 实例 `JY61P`（SCL/SDA 2 associatedPins） | API = `jy61p_init`（**器件初始化序列按页面原样**：寄存器解锁（0x69←{0x88,0xB5}）→Z 轴归零（0x01←{0x04,0x00}）→ 保存（0x00←{0x00,0x00}），再一轮解锁→角度归零（0x01←{0x08,0x00}）→保存，每步 delay_ms(200)——页面「网站说要延时三秒，经实验 200ms 也行」按页面 200ms）+ `jy61p_read_angles(float *roll, float *pitch, float *yaw)`（**页面 get_angle 换算保留**：读 0x3D 起 6 字节（Roll/Pitch/Yaw 各 2 字节 LSB 先），raw/32768.0×180.0 + ±180° 回绕（>180 减 360、<-180 加 360）；∫return 0=成功/1=读写应答失败——统一约定 0=成功；取消页面 printf/get_angle 返回值形态，角度经出参带回）+ `jy61p_read_raw(uint8_t data[6])` **可选**（页面 readDataJy61p 原始字节读取——底层只读 6 字节角度原始值，页面 readDataJy61p 语义原样；写寄存器族（writeDataJy61p）私有化（服务函数不需直接写寄存器——初化序列封装在 jy61p_init 内，notes 记录如需自定义寄存器写入可经引脚绑定…按需扩展））。**人工复核修正（记 notes）**：页面 `I2C_WaitAck` 在 while 轮询前未拉高 SCL（时序微瑕——SDA 采样须在 SCL 高电平窗口），照 sht30/sht20 页面正确版实现（SCL(1) 采样 + 10×5us 重试上限），行为与页面等价、真机留验证；页面 header `YAW_REG_ADDR 0x3F` 未用且标注有误（0x3F 为 Pitch 低字节）——不声明（页面 DO 宏未用不声明同例）。默认 SCL=**PA28**/SDA=**PA31**——与 IMU601 UART0（imu_uart 姿态互替）、FINGERPRINT_UART（身份）、HX711（称重）、SHT30 SDA（温湿度互…不同框）、MICROWAVE（微波雷达）重叠：姿态测量与身份/称重/温湿度/微波采集不同框、同选概率最低（姿态惯配双电机/舵机/显示/无线——**刻意不叠** motor 10 脚/编码器 4 脚（PA12/PA13/PB9/PA18/PB18/PA7/PA16/PA17/PB19/PB20）、servo PA7、step_motor PB24/PB6/PB7/PB8、显示 max7219 PB9/PA18/PB18、OLED PB2/PB3、无线 PA8/PA9/PA23/PA24/PA26/PA25、触摸/摇杆 PA22-27/PA9、语音 PB19/PB20、气体 PB18/PA14/PB9/PA18/PB20/PB24、报警 PA15、红外发射/接收 PA0/PA26——平衡车/云台惯配组合默认即不撞；也不叠 I2C_0 硬 I2C 脚 PA0/PA1——软 I2C×硬 I2C 同脚 = 物理冲突分组，批次 5 先例），同选时经引脚绑定消解 |
| `l298n` | control--l298n-motor-drive-module.md | **PWM×2（方向+调速形态）+ GPIO 使能**——L298N 三脚一组（IN1/IN2/EN） | 新 PWM 实例 `L298N_PWM`（TIMG12，C0=PA14/C1=PB24，clockPrescale=1 + timerCount=2000——32MHz/2000 ≈ 16kHz，页面 A 端口 1 路电机）+ 新 GPIO 实例 `L298N`（EN 输出，初始 SET = 使能高） | **决策：独立 l298n 模块（不并入 motor）**——接线/驱动芯片/场景差异大（TB6612 = 1.2A 轻量双路带编码器闭环；L298N = 2A 大电流双 H 桥、压降 ~1.5V、发热大、无编码器脚），notes 写明与 motor(TB6612) 的分工与适用场景（大电流/多路电机、无编码器闭环——平衡车/推车/闸机/重载）。API 对齐库风格：`l298n_init`（EN 置高 + 双通道 0 + startCounter）+ `l298n_set_duty(uint32_t duty)`（**0..L298N_PWM_PERIOD−1**，限幅——页面 speed 范围 0~per-1 语义）+ `l298n_set_direction(uint8_t dir)`（**1 正转 / 0 反转**，页面 dir 语义；两函数组合 = 页面 AO_Control 原样：dir=1 → C0=0/C1=duty，dir=0 → C0=duty/C1=0，页面 AO_Control 按页面原样实现（内部保留静态 duty，设置方向时重应用））；**单路（A 端口）范围**——页面仅实现 IN1/IN2（「IN3/IN4 内容类似」），B 端口同构扩展留待后续/多实例机制，notes 写明；页面 `DL_TimerG_setCaptureCompareValue` 按库内 motor.c 先例用 `DL_Timer_setCaptureCompareValue`（SDK 2.11 同义 API，motor 实证）。默认 **C0=PA14/C1=PB24**——与 DCC_100_PWM2（step_motor 步进脉冲，TIMG12 同外设——L298N 与步进驱动互替、同选概率最低故共用默认外设，同选时经引脚绑定换实例消解）、WS2812 IN（灯带）、SR04 TRIG（测距）、RC522 SCK（读卡门禁）、AGS10 SDA/soil（气体/土壤）、HC05 KEY、AT24C02 SCL、mq5、step_motor RST2 重叠——大电流驱动与步进/测距/读卡/存储/气体不同框、同选概率最低（**刻意与 motor 默认 10 脚错开**——两驱动同选概率低但可能并排使用（如 TB6612 小电机 + L298N 大电机同车），默认即不撞；也不叠显示（PB9/PA18/PB18/PA2/PB3）、无线（PA8/PA9/PA23/PA24）、温湿度/光照（PA12/PA13/PA28/PA31/PB6/PB7）、语音（PB19/PB20）、蜂鸣（PA15）——车类惯配组合），EN=**PA27**——与 HUIDU R2（灰度巡线）、ADC12_0 adcPin0（ir_distance MEM3）、TTP224 OUT4（触摸按键）重叠：使能脚与 8 路灰度巡线（巡线车惯用轻量 TB6612 故不同框）、模拟测距、触摸面板不同框、同选概率最低，同选时经引脚绑定消解；四件默认互不相撞（PA16/PA17 + PA28/PA31 + PA14/PB24/PA27 + PA8/PA9） |
| `open_mv4` | rf--open-mv4-camera.md | **真实 UART 接收（单向帧解析）**——页面 UART_1 9600 + RX 中断 → 本件按批次 4 fingerprint 结论改**轮询接收** | 新 UART 实例 `OPENMV4_UART`（默认 $assign=**UART1**、targetBaudRate=**9600**（页面案例）、enabledInterrupts=[] 轮询——无 IRQHandler 强符号） | **UART 放置决策（关键，按用户决策树取证后落定方案 ①）**：读批次 4 fingerprint 结论——SysConfig CLI 实证① 同一 UART 外设多实例 = Resource conflict；② UART **实例上限 4**（= UART0-3 外设数）；③ 母版 UART0-3 全被实例占用（UART0=IMU601+FINGERPRINT_UART、UART1=DIGIT_UART、UART2=DEBUG_UART+UWB_UART+HC05_UART、UART3=ZIGBEE_UART——7 个实例定义，每工程先裁剪、裁剪后至多 4 实例）。**方案选择：① 真实 UART 独立实例（照 fingerprint「裁剪后独占」先例）**——默认挂 UART1（页面原接线「PA8/PA9 附加串口 1」，与 DIGIT_UART（K230 直觉）同外设同脚：OpenMV4 与 K230 视觉互替、同选概率最低，单选裁剪后独占 UART1，同选时经引脚绑定换实例/换脚消解——与 FINGERPRINT_UART 挂 UART0 同构）;**现实约束记录**：UART 实例上限 4——open_mv4 与另 3 件 UART 模块（im_uart/uart/digit_uart/debug/uwb/zigbee/hc05/fingerprint 中任 3 件）同选 = 上限 4 内、4 件以上同选 = SysConfig CLI 拒绝（既有约束类，与 4+ 件 UART 同选现状同源，notes 写明「视觉互替类通常不与多 UART 同选」）；**方案 ②软 UART RX 边沿采样**（无先例、工作量最大、9600 位时序靠 GPIO 边沿 + 忙等采样且与主循环耦合——不开），**方案 ③并入 coord_detect 扩展**（帧格式差异大：coord_detect = K230 CSV 行帧 `B,<cx>,<cy>,<conf>,<x1>,<y1>,<x2>,<y2>`（逗号分隔 + 字母头 + 115200），open_mv4 页面 = `任意前缀 + [<cx>,<cy>] + \r\n`（方括号包裹 + 无置信度 + 9600）——两件视觉帧解析各有格式，不推荐强并（合并需双格式分支 + 波特率冲突 + 契约漂移风险），notes 写明差异）；API = `open_mv4_init`（清接收状态——页面 OpenMV4_usart_config 的 NVIC 使能随轮询裁剪（无 ISR））+ `open_mv4_flush`（丢弃旧帧）+ `open_mv4_read_frame(int *cx, int *cy, float *confidence)`（**页面 Openmv4DataAnalysis 按行分帧原语保留**（'[' 起始/'\]' 结尾查找、缓冲上限），解析出两整数中心坐标——**补页内缺失的数值解析**（页面只找头尾 + printf 未做数值提取）；**置信度出参 = 1.0f 固定**（页面帧格式无置信度字段——OpenMV 侧阈值命中才 `uart.write`，notes 写明；与 coord_detect 出参形态对齐（cx/cy/confidence + detected 语义）方便骨架消费）；单值帧 `[%d]`（页面案例二循迹偏差）→ cx=pos、cy 置 0（占位，notes 写明）；帧首'[' 前前缀（页面 `Maximum color block position : `）自动跳过；数据缓冲 128 字节（页面 200 缩编）+ 行分帧状态静态化（坐标_detect parse 先例——驱动层分帧非业务状态机，ADR 0009 合规））；页面 `UART_1_INST_IRQHandler`（接收中断缓冲）随轮询裁剪——页面 `HardFault_Handler` main 调试件剔除；**页内 Python 块只作参考素材**（帧格式来源：案例一 `[%d,%d]`、案例二 `[%d]`、案例三/四/五为矩形/激光——本件只落案例一/二形态，矩形四角/激光定位帧格式可后续扩展，notes 写明）；默认 TX=PA8/RX=PA9（页面原脚，与 DIGIT_UART 默认同脚——互替低同选，同选经引脚绑定消解；PA8/PA9 亦与 IR_BEAM/HC05 STATE/MLX90614 SDA、JOYSTICK SW/NRF24L01 MISO/MLX90614 SCL 重叠——视觉与红外对射/蓝牙/测温/手动输入不同框同选概率最低） |

### 默认脚与重叠全景（2026-09-11 定稿）

| slug | 默认脚 | 重叠主体（同选概率最低） |
|---|---|---|
| `sht20` | SCL=PA16 / SDA=PA17 | DC_MOTOR 编码器 AA/AB + RC522 MOSI/MISO + ADS1115 SCL/SDA |
| `jy61p` | SCL=PA28 / SDA=PA31 | IMU601/FINGERPRINT_UART/HX711/SHT30/MICROWAVE |
| `l298n` | C0=PA14 / C1=PB24 / EN=PA27 | DCC_100_PWM2（TIMG12 同外设）+ WS2812 + SR04 + RC522 SCK + AGS10/soil/step/hc05/at24c02/mq5、HUIDU R2 + ir_distance + TTP224 OUT4 |
| `open_mv4` | TX=PA8 / RX=PA9 | DIGIT_UART（UART1 同外设同脚）+ IR_BEAM + HC05 STATE + MLX90614 SDA / JOYSTICK SW + NRF24L01 MISO + MLX90614 SCL |

- **四件默认互不相撞**（PA16/PA17 + PA28/PA31 + PA14/PB24/PA27 + PA8/PA9）——温湿度+姿态+驱动+视觉罕有全同框；两两组合（温湿度+驱动 = 环境站、姿态+驱动 = 平衡车、视觉+驱动 = 视觉车）默认即不撞。
- 与既有默认重叠计数更新（test_pin_bindings.py 刻意重叠表）：**PA16 3→4 / PA17 3→4**（sht20）、**PA28 4→5 / PA31 5→6**（jy61p。PA31 与 JP61P——姿态与温湿度/身份/称重同一「低频采集」池，sht30 同池先例）、**PA14 5→6 / PB24 5→6 / PA27 3→4**（l298n）、**PA8 4→5 / PA9 4→5**（open_mv4）、**UART1 1→2**（DIGIT_UART + OPENMV4_UART）、**TIMG12 1→2**（DCC_100_PWM2 + L298N_PWM——外设级重复登记）。

### 网盘依赖（本批无）

本批四件页内源码完整（v7 审计通过）。例外项随 notes 记录、不阻塞：全部未上板（软 I2C 时序/JY61P 寄存器序列/9600 帧解析真机验证留后续）。

## 测试决策

照批次 1-9 先例逐件：

- `tests/test_pins.py`：
  - `MSPM0_DEFAULT_MAP` 增 9 条映射（sht20 SCL/SDA、jy61p SCL/SDA、l298n C0/C1/EN、open_mv4 TX/RX；l298n C0/C1 走 `("L298N_PWM","ccp0Pin"/"ccp1Pin")` 外设键、EN 走 `("L298N","EN")` 组名、open_mv4 走 `("OPENMV4_UART","txPin"/"rxPin")`）；
  - 无引脚字面量豁免新增（四件全走 syscfg 生成宏；`UART_[123]`/`TIM[234]_CH[1-4]` 字面量不可出现——open_mv4 用 OPENMV4_UART_INST、l298n 用 GPIO_L298N_PWM_C0_IDX）。
- `tests/test_pin_bindings.py` 刻意重叠表更新（上表 8 行 + UART1/TIMG12 外设行）。
- `tests/test_syscfg_prune.py` 增 SHT20/JY61P/L298N_PWM/L298N/OPENMV4_UART 实例保留（单选各自）/裁剪（hc05 单选）断言。
- 新增 `tests/test_module_sht20.py` / `test_module_jy61p.py` / `test_module_l298n.py` / `test_module_open_mv4.py`（照 test_module_joystick.py 模板）：manifest 结构（仅 mspm0 + 依赖 + 角色默认 + notes 关键子串）+ mspm0 单选生成（syscfg 含实例、模块文件落盘、main.c 调 init/服务函数过静态门禁）+ 关键守卫：
  - sht20：`175.72f`/`46.85f`/`125.0f`/`6.0f` 系数守卫、`0xF3u`/`0xF5u` 命令字、`0xFFFC` 掩码修正、`0x40`（`0x80u` 写/`0x81u` 读）、`<= 50 × 2ms` 重试守卫（`SHT20_READ_RETRY_MAX`/`SHT20_READ_RETRY_MS`）、无 CRC 调用（`sht20_crc8` 不出现）、无 printf/IRQHandler；
  - jy61p：`0x50` 地址（`0xA0`/`0xA1`）、`0x69`/`0x01`/`0x00` 寄存器序列 + `{0x88, 0xB5}`/`{0x04, 0x00}`/`{0x08, 0x00}` 数据 + 6×200ms 延迟、`32768.0f`/`180.0f` 换算 + ±180 回绕（`- 360.0f`/`+ 360.0f`）、`0x3D` 寄存器、`6` 字节读取、读失败统一约定 0/1、无 printf；
  - l298n：`DL_Timer_setCaptureCompareValue` 调用守卫（页面 DL_TimerG 改）、`C0`/`C1` IDX 宏、dir 语义（`1` 正转 → C0=0/C1=duty）、`L298N_PWM_PERIOD` 限幅、EN 置高（`L298N_EN` setPins）、无编码器/无 GPIO 中断断言（组名不出现 DC_MOTOR）；
  - open_mv4：**帧解析纯函数单测（最高既有接缝）**——`openmv4_frame_parser(line) -> (ok, cx, cy)` Python 镜像（伪帧序列：`[123,456]` / `Maximum color block position : [12,34]\r\n` / `[5]` / 坏帧 `[abc` / 空行 / `[1,2,3]` 越界 → 结果坐标断言，页内「找 '[' 找 ']'」原语镜像）+ 源码文本守卫（`9600` / `OPENMV4_UART_INST` / `isRXFIFOEmpty` 轮询 / 无 `IRQHandler` / `0.5`? 无——置信度 `1.0f`）+ manifest notes 子串（「UART1」「实例上限」「coord_detect 差异」）。
- 编译级验收：复制 `run_joystick_matrix.py` 改 slug（四件各一，放 .scratch/wiki-modules-batch10/：**open_mv4 单选含 UART1 实例 → PA8/PA9 过 SysConfig CLI；l298n 单选含 PWM 实例 TIMG12 → PA14/PB24 过 CLI（TIMG12 时钟/通道合法实证）**），gmake 真编译（`C:/ti/ccs2050`）0 error 硬门槛、模块自身 warning 0；结果回写 manifest verified/notes。

## 范围外

- stm32 平台条目、上板真机验证（真机留后续，notes 注明）、新 UART/TIMG 外设（本批沿用「裁剪后独占」挂靠既有外设——UART0-3/TIMG0/6/7/8/12 现役范围）。
- open_mv4 页内 Python 侧（OpenMV 脚本）不落码——只作帧格式参考素材（参考文件库锚定另议）；矩形四角（案例三/四）/激光定位（案例五）帧格式扩展、`[%d]` 循迹单值帧专用 API——留后续（notes 写明）。
- JY61P 串口控制方式（默认 9600 备选）——本件按页面 IIC 例程；串口 JY61P 帧（0x55 帧头）与 imu_uart 601 帧不同族，留后续。
- L298N B 端口（IN3/IN4/ENB）与双路 API——页面仅 A 端口演示，同构扩展留后续/多实例机制。
- 正文内嵌段落（行拆散版）不作为提炼源；open_mv4 的 `[%d]`/`[%d,%d]` 之外的自定义格式不承诺。
- 后续批次地图（另立工单）：11 = MQ 同构快补收尾（mq-3/4/6/7/8/9 + ms1100 薄封装——同 mq5/mq2 结构照抄，若判定重复度溢出价值可砍件并记 spec）；12 = 彩屏线（需网盘厂家例程后开工——链接在 sources/materials/lckfb-地猛星移植手册/网盘索引.md）。

## 补充说明

- 排序依据：批次 1-9 决策记录延续——本批按「无网盘依赖 + 页内源码完整」先做：sht20（软 I2C 打样，sht30 姊妹件）→ jy61p（同软 I2C）→ l298n（PWM+GPIO）→ open_mv4（真实 UART——含 UART 放置决策取证）。
- 审计脚本 `.scratch/wiki-materials/audit_v7.py` 可复跑；本批四件均在 v7 全自洽 58 篇内（不在 12 篇真·页外名单）。
- 工单：`issues/01-module-sht20.md` → 02 jy61p → 03 l298n → 04 open_mv4（互相独立；实施按简→繁）。
- 词表预算：四件入库后按 batch9 先例实测 wordlist wire 大小，超 WORDLIST_PROMPT_BYTES（6600）上限则按预算链（llm.py/budget.py）上调并记 spec；词表段全量送达契约（test_wordlist_segment）不截断。
- 完成后：全量测试套件 + 批次 1-10 全部 **39 件**一致性快检（`.scratch/wiki-modules-batch10/sweep_39_modules.py`——照 sweep_35_modules.py 更新）+ 批次 1-10 全部 39 件 code-review 收尾 + CONTEXT.md 平台行补录四件 + 中文提交（.githooks/commit-msg 强制中文；.ps1 若新增按 UTF-8 with BOM 存）。

## 实施结论（2026-09-11，收尾补记）

- 四件编译矩阵全部 PASS（0 error/0 warning）：sht20、jy61p、l298n（**PWM 实例 TIMG12 + PA14/PB24 + EN PA27 经 SysConfig CLI 实证据合法**——与 gp2y1014au PA1 先例同型）、open_mv4（**UART1/9600/PA8/PA9 合法**）；verified=true 全部回写；未上板（notes 注明）。
- 默认脚定稿（spec 决策表与原定一致）：sht20=PA16/PA17、jy61p=PA28/PA31、l298n=PA14/PB24/PA27、open_mv4=PA8/PA9——四件互不相撞；与既有默认重叠计数全部同步 test_pin_bindings 刻意表（PA16/17/28/31/14/24/27/8/9 + UART1 + TIMG12）。
- **词表预算实测**：默认词表完整 wire 6565（> 6434 fit 上限 6600−166——test_wordlist_segment 契约红证）→ 按 batch5/7/8/9 口径上调 WORDLIST_PROMPT_BYTES **6600→6800**（fit 上限 6634 ≥ 6565 全量送达 + 69B 余量）；词表段全量 6565 比旧截断形态 6600 **少 35B**——最坏形态总量 −35B，REFERENCE_FULLTEXT_BYTES 61000 不动（2KB 边界余量保持）。
- 39 件一致性快检（sweep_39_modules.py）全 OK；全量测试套件 3507 passed。
- syscfg_model.py pwm 落点匹配扩展「按 slug 反查实例」（DCC_100_PWM2/L298N_PWM 同 TIMG12/PA14 区分）——修正 + 显式判例测试；UART 换位测试随 open_mv4 默认 UART1/同默认槽位规则同步（open_mv4 随 digit_uart 槽位族绑走）。
- 工单 01-04 全部实施完毕（状态 resolved、结论含提交号/关键发现）。

## code-review（2026-09-11，双轴并行评审，固定点 4dac46c8——code-review skill 随收尾执行、结果回填至此，与批次 9 同款「评审后置、结果入 spec」口径）

- **标准轴**：**0 硬违规**（四件均过 ADR 0009 纯驱动切片/ADR 0005 四要素/引脚宏参数化/中文规范——open_mv4 分帧态为驱动层非业务状态机）；4 项判断（① 流程顺序——评审在工单 resolved 后执行（批次 9 同款口径，结果回填）；② syscfg_model.py docstring「外设角色尾字段唯一」与实现漂移——**已整改**（docstring 同步 pwm 尾字段不再唯一）；③ jy61p 三段角度换算同构（Duplicated Code）——**已整改**（提取 `jy61p_angle_from_raw`）；④ syscfg_model.py pwm 分支 `known` 兜底死路径（Speculative Generality）——**已整改**（未登记 slug 改为大声 KeyError——数据漂移显性化）；模块间软 I2C 原语复制（12+ 份自含）为明示先例标准接受、l298n 周期双源（L298N_PWM_PERIOD 与 syscfg timerCount）为 motor limit_duty 先例标准允许——不作整改、记录）。
- **规格轴**：实现与 spec/工单逐条一致；1 处契约偏差**记 spec 修正**（sht20_read 公开错误码 = 实现 0=成功/1=温度段失败/2=湿度段失败（分段码——页面单值读合并两段、各段内部 1/2/3 细分码保留于 sht20_measure_once 并已随测试断言），原 spec 的「1-5 细分码」形态对两段测量有歧义——spec 行已按实现契约修订（实现自洽且更实用，超时/总线段细粒度保留内部）；1 处测试补强）——地址写读形态守卫补强（sht20 0x80/0x81、jy61p 0xA0/0xA1——`(addr << 1) | 0u/1u` 表达式守卫）；其余核对通过项（默认脚/syscfg 实例/依赖/公式/寄存器序列/帧形态/词表/测试/预算）全部一致；未见范围蔓延。
- **39 件收尾评审（批次 1-10）**：**0 硬违规**；4 项判断（① I2C 地址表述口径混用——bh1750 kit 0x46（8bit 写地址）vs sht30/sht20/jy61p 7bit 地址，建议统一 7bit 并注明 `<<1`——非本批件，留待后续统一；② max7219 source_url 只列数码管页（点阵页在 notes）——非本批件；③ adc 模块（39 件外）notes 口径漂移——非本批件；④ sht20 kit 地址/no-hold 依据 SHT2x 数据手册（页面未含）——本件 header/notes 已注明「SHT2x 数据手册 + 立创页面」来源，记录不作更改）；批次 10 四件重点评审通过（纯驱动/出参收敛/无 printf/main/notes 编译矩阵记录/手册地址寄存器逐项对上/wordlist 挂接类别正确）。
