# 批次 3「显示/执行」— 立创 wiki 地猛星手册模块批量入库

## 问题陈述

批次 1「遥控/通信」四件（joystick/hc05/nrf24l01/ir_remote）与批次 2「传感器常用」四件（dht11/us016/bh1750/ir_distance）已入库。`lckfb-地猛星移植手册/` 剩余约 62 篇中页内自带完整驱动源码的页面，模块库仍缺**显示/执行**两类常见件——用户做计分/计时/数据显示题（数码管/点阵）、多路舵机执行（16 路舵机板）、双机红外遥控（发射端）时，AI 不知道库里有驱动，只能当"需自备"。

按用户裁决：批次 3 = **显示/执行**四件（四篇手册页面：8 位数码管、MAX7219 4合1 点阵、16 路舵机驱动、红外解码编码）——全部页内源码完整（v7 全自洽）、无需网盘。

## 方案

照批次 1/2 已确立管线，每件一个工单：手册「代码块」提炼完整 bsp（正文内嵌段落禁用）→ 纯驱动切片改造（去 main/printf、API 规范化、ADR 0009 无状态机）→ 母版 syscfg 新实例 + `syscfg_instances.py` INSTANCE_CONSUMERS 登记 → manifest（dependencies/pins/kit+source_url/notes 含手册路径+原页+网盘链接+改造要点+与既有 servo 模块区分说明）→ wordlist.json 对应分类补录（lib_modules 挂接）→ 测试（`test_module_<slug>.py` 照 test_module_joystick.py 模板 + test_pins.py / test_pin_bindings.py / test_syscfg_prune.py 增断言）→ 编译矩阵（复制 run_joystick_matrix.py 改 slug：单选生成 → SysConfig CLI → gmake 0 error/0 warning 硬门槛）→ verified=true 回写 → 中文提交 → 逐件 code-review。

## 用户故事

1. 作为做题用户，我选中 `max7219`/`pca9685`/`ir_remote_tx` 后，工具自动分配默认脚，生成工程打开即可编译，可调用 init + 服务函数。
2. 作为做题用户，我做计分/计时/数据数字显示（8 位数码管或 4合1 点阵）、多舵机机械臂（16 路舵机板）、双机红外遥控/模拟家电遥控时，不用再读器件手册、不用自写 38kHz 时序与 I2C 位操作。
3. 作为维护者，查看每个新条目能看到平台条目（verified/kit/source_url/网盘链接/改造要点/编译记录），可溯源到手册。

## 实现决策

### 既定事实（勿重新调研，批次 1/2 已实证）

① 母版 `ADC12_0` 已是 sequence 四通道（endAdd=3：MEM0=adc / MEM1-2=joystick / MEM3=ir_distance），本批**不新增 ADC 件**（软 I2C/软 SPI 只是 GPIO 实例，与 ADC12_0 无关）；
② 地猛星 2×20 排针 31 个 IO 全被默认布局占用——新模块默认脚按「同选概率最低者与既有默认重叠」，同选经引脚绑定消解；
③ 母版 GPIO 中断全走 GROUP1 一个向量且被 KEY/motor 编码器消费——本批三件全部**轮询/忙等**，不注册 GPIO 中断；
④ 编译矩阵工具链 `C:/ti/ccs2050`、SysConfig CLI `C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat`、探针脚本先例 `.scratch/wiki-modules-batch1/`；
⑤ 母版软 I2C 先例 = AHT10（PB6/PB7，SDA 方向运行时切换）；软 SPI 先例 = nrf24l01（6 脚全 GPIOA 单 PORT 宏）；位时序先例 = ws2812（delay_cycles 按 CPUCLK_FREQ 换算）。

### 共性（三件一致）

- **仅 mspm0 平台条目**（stm32 缺条目 = 生成时 missing 警告，批次 1 先例）；`hardware_bound: false`；`verified` 初始 false，编译矩阵通过转 true；未上板（notes 注明）。
- **代码提炼**：从手册「代码块」章节抽完整 bsp，改造为 `xxx_init()` + 服务函数，去 main/printf，函数名规范化（去 `Write_Max7219`/`Set_` 菜市场命名按库风格重命名），全局状态收敛为模块内静态 + 入参/出参。
- **时序**：微秒/毫秒延时走库内 `delay` 模块（`dependencies: ["delay"]`，仅确实需要时——max7219 软 SPI 位操作不延时，依赖空）；**不占 TIMER 实例**（TIMG0/6/7/8/12 已全占；pca9685 的 PWM 由芯片内部振荡器生成、主控只写寄存器——页面"1.6kHz 可调频 PWM 输出"即此义）；**不注册 GPIO 中断**（GROUP1 只一路且被 motor 编码器独占）。
- **引脚宏参数化**：不写死立创宏名（`MAX7219_PORT` 等），按 manifest pins 角色 + 母版 syscfg 实例宏名对齐（`<实例>_<引脚>_PIN`/`_IOMUX`，aht10 编译矩阵实测）。
- **默认脚**：按「同选概率最低者与既有默认重叠」分配（重叠对写入 `test_pin_bindings` 刻意重叠表）；ir_remote_tx 特例：与 ir_remote 默认 PA26 **刻意错开**（发/收本就常配对）。
- **wordlist**：显示模块/执行机构/遥控接收按条目补录（名称 + `lib_modules` 挂接），硬件词表 models 加词条。

### 各件决策

| slug | 手册 | 外设形态 | 母版 syscfg 实例 | 关键决策 |
|---|---|---|---|---|
| `max7219`（**先做**） | screen--8-bit-led-tube.md + screen--max7219-matrix-display.md（**合并**） | 软 SPI 位操作 3 脚（DIN/CLK/CS 输出——nrf24l01 软 SPI 先例族） | 新 GPIO 实例 `MAX7219`（3 associatedPins 全 OUTPUT） | **单模块双形态**（同一芯片、驱动内核同源）：数码管 8 位 = BCD 译码形（`max7219_write_digit`：位 1-8，值 0-9 / 0x0F 熄灭；级联 2 片=16 位）、4合1 点阵 = 无译码形（`max7219_write_matrix`：8 行字模 × 级联片数 1-4，行 0 = 寄存器 0x01）；`max7219_init(form, brightness)` 一个 init 按形态配译码/扫描/亮度；另出 `max7219_write_reg`（底层、级联片寻址）/`max7219_clear`（按形态全灭）/`max7219_set_chip_count`；**digit_led 并入见下**；默认 DIN=PB9 / CLK=PA18 / CS=PB18——与 DC_MOTOR AIN1/AIN2/BIN1 重叠（大数字显示/计分计时与双电机小车同选概率最低——小车状态显示惯走 OLED，数字牌/固定装置与车类不同框；PA18 兼 BSL 脚，作输出无碍） |
| `pca9685` | control--16-ch-servo-drive-module.md | 软 I2C 位操作（2 GPIO，照 AHT10 先例，不占硬件 I2C 外设）+ 16 路 PWM 寄存器 | 新 GPIO 实例 `PCA9685`（SCL 输出 / SDA 双向运行时切换） | API = `pca9685_init(freq_hz)` + `pca9685_set_pwm(ch, width)`（12bit 计数，ON=0）+ `pca9685_set_angle(ch, angle)`（0-180° ↔ 0.5-2.5ms，**与库内 servo 模块同口径**——servo 是 TIMG8 硬件 PWM 单路（板载 PM 封装仅 1 路 PWM 不足时），pca9685 是 16 路 I2C 寄存器扩展，二者互补不重复，manifest notes 写清区别）+ `pca9685_set_freq` + `pca9685_set_address`（A5..A0 = 0-0x3F，写地址 = (0x40+A5)<<1，页面 62 板级联）；频率 prescale = round(25e6/4096/freq)-1（睡眠→写→唤醒→恢复 MODE1|0xA1，页面 FLOOR 公式即此——Excel FLOOR 注释剔除）；默认 SCL=PB6 / SDA=PB7——与 STEP_MOTOR SLP2/DIR2、HUIDU R3/R4、AHT10 SCL/SDA、DHT11 DATA 重叠（16 路舵机多自由度执行与温湿度采集/步进单轴执行（互替）/巡线车同选概率最低） |
| `ir_remote_tx` | rf--Infrared-decoding-coding-module.md | GPIO 输出 + 38kHz 载波位操作（半周期 13us 忙等翻转，不占 TIMER——ir_remote/ws2812 先例） | 新 GPIO 实例 `IR_TX`（OUT 输出，初始 CLEARED = 空闲低） | 页面形态 = 「MCU+发射头+接收头、UART 指令」模块（帧头 A1/通用 FA + 操作位 F1 发射 / F2 改地址 / F3 改波特率 + 反馈）——**UART 指令解析归生成骨架（ADR 0009）**（骨架 = 接 UART 模块 RX 中断 + 环形缓冲，解析 5 字节指令还原页面功能），模块只出 `ir_tx_init` + `ir_tx_send(address, command)`（NEC 帧：9ms+4.5ms 引导 / 地址+反码+命令+反码 4 字节 / 560us 结束位；字节内位序 MSB 先——**与批次 1 ir_remote 解码口径一致**，标准 NEC 为 LSB 先，控市售设备改 IR_TX_MSB_FIRST 宏）+ `ir_tx_send_repeat()`（9ms+2.25ms+560us 重复码，长按节奏 = 调用方循环，无状态机）；默认 TX=**PA0**——与 I2C_0 SDA（ml_mpu6050 姿态）/板载 LED 重叠（红外发射链与姿态采集同选概率最低；板载 LED 随载波闪烁可作发射指示），且与 ir_remote 默认 PA26 刻意错开（发射/接收本就常配对——双选默认即不撞；notes 说明配对关系与 remap 建议：发/收两脚建议绑相邻排针、共地供电） |
| `digit_led`（视工单 01 决策） | screen--8-bit-led-tube.md | — | — | **决策：并入 max7219**（工单 01 主形态之一 = 8 位数码管，与 digit_led 所指相同）。重复驱动的取舍：两页面同芯片 MAX7219、驱动内核（Write_Max7219 位序 + 寄存器族）完全同源——拆两个模块 = 两份内核 + 两套 GPIO 实例 + 两处 wordlist 挂接 + 同选链接期重复定义（Write_Max7219 强符号）风险；单模块双形态（form 参数 + write_digit / write_matrix 两族服务函数）费用 = 一个枚举参数，**推荐**（不推荐逐件拆分；若坚持拆分必须按此 spec 写明取舍——本 spec 已定不拆） |

### 网盘依赖（本批无）

本批页面页内源码完整（v7 审计通过）。例外项随 notes 记录、不阻塞：全部未上板（38kHz 载波/软 I2C 时序/级联链序真机验证留后续）。

## 测试决策

照批次 1/2 先例逐件：

- `tests/test_pins.py::MSPM0_DEFAULT_MAP` 增映射（max7219 三脚 / pca9685 两脚 / ir_remote_tx 一脚，均 GPIO 组实例定位）；
- `tests/test_pin_bindings.py` 刻意重叠表更新（PB9/PA18/PB18/PA0 各 1→2 新条目，PB6 3→4、PB7 4→5 计数与注释）；
- `tests/test_syscfg_prune.py` 增 MAX7219/PCA9685/IR_TX 实例保留/裁剪断言；
- 新增 `tests/test_module_max7219.py` / `test_module_pca9685.py` / `test_module_ir_remote_tx.py`：manifest 结构（仅 mspm0、依赖、pins 默认集）+ 单选生成（syscfg 含实例 + 模块文件落盘 + main.c 调 init/服务函数过静态门禁）；
- 编译级验收：复制 `run_joystick_matrix.py` 改 slug，gmake 真编译（`C:/ti/ccs2050`）0 error 硬门槛、模块自身 warning 0；结果回写 manifest verified/notes。

## 范围外

- 其余显示件（彩屏 6 件 + 0.96 SPI 单色需网盘——批次 7 先例）、其余执行件（继电器/语音模块）、红外对拷（市售设备 LSB 位序自动适配）。
- stm32 平台条目、上板真机验证（真机留后续，notes 注明）、新 UART/ADC/TIMER/硬件 I2C/硬件 SPI 外设实例（本批全部 GPIO 实例，不占外设）。
- 正文内嵌段落（行拆散版）不作为提炼源。
- 4合1 点阵演示字模表（disp1 12 组汉字/数字）不随模块入库——字模属界面数据，骨架/用户自备（notes 建议）。

## 补充说明

- 排序依据：批次 1/2 决策记录延续——本批按显示/执行常用度排序：max7219（先做，含 digit_led 决策）→ pca9685 → ir_remote_tx；digit_led 并入 max7219（工单 04 只落决策档，无独立实施）。
- 审计脚本 `.scratch/wiki-materials/audit_v7.py` 可复跑；本批页面均在 v7 全自洽清单内。
- 工单：`issues/01-module-max7219.md` → 02 pca9685 → 03 ir-remote-tx → 04 digit-led（并入决策档）。
- 完成后：全量测试套件 + 批次 1+2+3 全部 12 件 code-review 收尾 + CONTEXT.md 平台行补录 + 中文提交（.githooks/commit-msg 强制中文；.ps1 若新增按 UTF-8 with BOM 存）。
