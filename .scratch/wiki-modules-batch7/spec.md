# 批次 7「气体/空气传感器第一组」— 立创 wiki 地猛星手册模块批量入库

## 问题陈述

批次 1「遥控/通信」（joystick/hc05/nrf24l01/ir_remote）、批次 2「传感器常用」（dht11/us016/bh1750/ir_distance）、批次 3「显示/执行」（max7219/pca9685/ir_remote_tx）、批次 4「语音/身份」（jq8900/syn6288/rc522/fingerprint）、批次 5「I2C 增强件」（ads1115/tcs34725/mlx90614/at24c02）、批次 6「环境监测/温度补充第一组」（ds18b20/sht30/mq2/ttp224）共 23 件已入库。`lckfb-地猛星移植手册/` 剩余页中**气体/空气传感器第一组**四篇页内自带完整驱动源码（v7 审计自包含，.scratch/wiki-materials/audit_v7.py 自包含清单已确认）：MQ-135 空气质量（AO 模拟量）、MQ-5 液化气/天然气（AO 模拟量）、SGP30 空气 TVOC/CO2e（软 I2C）、AGS10 有害气体 TVOC（软 I2C）——模块库仍无对应条目：用户做气体检测/空气质量/可燃气体报警题时，AI 不知道库里有驱动，只能当"需自备"。

按用户裁决：批次 7 = **气体/空气传感器第一组**四件——全部页内源码完整（v7 全自洽）、无需网盘。

## 方案

照批次 1-6 已确立管线，每件一个工单：手册「代码块」提炼完整 bsp（正文内嵌段落禁用）→ 纯驱动切片改造（去 main/printf、API 规范化、ADR 0009 无状态机——校准/连续采集流程归生成骨架）→ 母版 syscfg（软 I2C = GPIO 实例 2 脚；ADC = 仅当独立 MEM 时改 ADC12_0 通道与 endAdd）+ `syscfg_instances.py` INSTANCE_CONSUMERS 登记 → manifest（dependencies/pins/kit+source_url/notes 含手册路径+原页+网盘链接+改造要点+与库内同类分工（温湿度/气体））→ wordlist.json 补录（感知传感器，lib_modules 挂接；MQ-135/MQ-5/SGP30/AGS10 与既有 MQ-2 并列）→ 测试（`test_module_<slug>.py` 照 test_module_joystick.py 模板 + test_pins.py / test_pin_bindings.py / test_syscfg_prune.py 增断言；ADC 换通道后旧断言全量同步）→ 编译矩阵（复制 run_joystick_matrix.py 改 slug：单选生成 → SysConfig CLI → gmake 0 error/0 warning 硬门槛）→ verified=true 回写 → 中文提交 → 逐件 code-review。

## 用户故事

1. 作为做题用户，我选中 `mq135`/`mq5`/`sgp30`/`ags10` 后，工具自动分配默认脚，生成工程打开即可编译，可调用 init + 服务函数读气体浓度。
2. 作为做题用户，我做完空气质量/可燃气体检测（相对浓度百分比）与 TVOC/CO2e 数字量气体测量（SGP30/AGS10）时，不用再读器件手册、不用自写时序。
3. 作为维护者，查看每个新条目能看到平台条目（verified/kit/source_url/网盘链接/改造要点/编译记录/与库内 mq2/aht10/sht30 等分工），可溯源到手册。

## 实现决策

### 既定事实（勿重新调研，批次 1-6 已实证 + 本批新取证）

① 母版 `ADC12_0` 已是 sequence 四通道（endAdd=3：MEM0=adc+us016+mq2 薄封装共读 / MEM1-2=joystick / MEM3=ir_distance）——**本批 mq135/mq5 走独立 MEM 模式**（ir_distance 先例；mq2 的 MEM0 薄封装共读与本批同选会撞同一物理通道，独立通道使多路气体同选时各器件物理通道独立、无共读冲突）；② SysConfig 拒绝同一 UART 外设多实例——本批无 UART 件；③ 地猛星 2×20 排针 31 个 IO 全被默认布局占用——新模块默认脚按「同选概率最低者与既有默认重叠」，同选经引脚绑定消解；④ 母版 GPIO 中断全走 GROUP1 一个向量且被 KEY/motor 编码器消费——本批全部轮询，不注册中断；⑤ 软 I2C 先例 aht10/批次 5 四件/sht30（默认脚已占 PB6/PB7、PA16/PA17、PA23/PA24、PA9/PA8、PB24/PB8、PA12/PA13、PA28/PA31——本批新软 I2C 再挑「同选概率最低」脚且刻意不叠以上全部）、软 SPI 先例 nrf24l01/max7219/rc522、软 UART TX 先例 jq8900/syn6288、忙等不占 TIMER（TIMG0/6/7/8/12 全占）；⑥ 工具链 `C:/ti/ccs2050`、SysConfig CLI `C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat`；⑦ 页内符号异常/器件正确性缺漏→人工复核、修正并记 notes（ir_remote 反码校验、nrf24l01 L01 缺陷先例）。
**本批新取证（2026-09-08 SysConfig CLI 实证）**：裁剪上下文（单选生成后）里 ADC12_0 加 MEM4-7（adcPin6=PB20/adcPin5=PB24/adcPin7=PA22/adcPin12=PA14）全部被 CLI 接受（仅 info 级提示）——通道选择无 SysConfig 级障碍；全量母版（未裁剪）整体过 CLI 有 110 个资源冲突（UART 同外设多实例/同脚分属多外设）——母版从来不被整体编译，冲突由裁剪 + 引脚绑定消解（既定事实在生成链中的既有前提，非本批新增约束）。地猛星板上 ADC0 可用通道/脚：CH0=PA27（MEM3 已占）、CH1=PA26（MEM1）、CH2=PA25（MEM2）、CH3=PA24（MEM0）、CH5=PB24、CH6=PB20、CH7=PA22、CH12=PA14（芯片通道→脚映射按 SysConfig 设备数据 reverseMuxes 反查）——本批取 CH6/CH5。

### 共性（四件一致）

- **仅 mspm0 平台条目**（stm32 缺条目 = 生成时 missing 警告，批次 1 先例）；`hardware_bound: false`；`verified` 初始 false，编译矩阵通过转 true；未上板（notes 注明）。
- **代码提炼**：从手册「代码块」章节抽完整 bsp，改造为 `xxx_init()` + 服务函数，去 main/printf，函数名规范化（去 `ADC_MQ135_Init`/`Get_Adc_MQ135_Value`/`SGP30_Read`/`AGS10_IIC_Start` 菜市场命名按库风格重命名），全局状态收敛为模块内静态 + 出参指针（sgp30 返回 uint32_t 打包值收敛为双出参；ags10 返回值与错误码混用收敛为出参+状态）。
- **时序**：微秒/毫秒延时全走库内 `delay` 模块（`dependencies: ["delay"]`）；**不占 TIMER**（TIMG0/6/7/8/12 已被全占，dht11/ir_remote_tx 先例）；**不注册 GPIO 中断**（软 I2C 轮询，GROUP1 被 motor 编码器独占先例）。
- **ADC 轮询**：页面 `ADC12_0_INST_IRQHandler` + `gCheckADC` 标志位按 joystick/ir_distance 先例改经 adc 模块 API 轮询读（`adc_get(ADC_1, ADC_Channel_<N>)`——共享实例 IRQHandler 强符号唯一；`dependencies: ["adc"]`）。
- **引脚宏参数化**：按 manifest pins 角色 + 母版 syscfg 实例宏名对齐（`<实例>_<引脚名>_PIN`/`_IOMUX`，SysConfig 命名 `<实例>_<引脚名>_IOMUX`，aht10 编译矩阵实测；跨端口多脚实例无合并 PORT 宏，按引脚名分派 `<实例>_<引脚名>_PORT/PIN`，max7219 先例）。
- **默认脚**：按「同选概率最低者与既有默认重叠」分配；本批四件默认**互不相撞**（气体检测器 = MQ-135/MQ-5 模拟量 + SGP30/AGS10 数字量多气体组合，默认即不撞）；重叠对写入 `test_pin_bindings` 刻意重叠表。
- **wordlist**：感知传感器组补录四件（名称 + `lib_modules` 挂接，与 MQ-2 并列），models 加词条。

### 各件决策

| slug | 手册 | 外设形态 | 母版 syscfg 实例 | 关键决策 |
|---|---|---|---|---|
| `mq135` | sensor--mq-135-sensor.md | ADC 模拟量（AO 输出，电压 → 百分比） | **无新 GPIO 实例**——ADC12_0 **sequence 开 MEM4**（**endAdd 3→4**、`adcMem4chansel=CHAN_6`、`adcPin6=PB20`） | **独立 MEM 通道（ir_distance 先例）而非 mq2 的 MEM0 薄封装**——理由：多路气体同选时各器件物理通道独立、无共读冲突（mq2 薄封装共读 adc 模块 MEM0，与 mq135 同选会撞同一物理通道——绑定槽位冲突检查强制同脚）；页面原脚 PA27（A0_0）已归 ir_distance MEM3，默认 PB20（A0_6，地猛星板上剩余 ADC 脚中同选概率最低——与 DC_MOTOR BB/SYN6288 TX 重叠，2→3）。API = `mq135_init`（adc_init 转 MEM4）+ `mq135_read_percent`（出 float 0-100%——`value/4095×100` 页面原式，5 次快速平均照 mq2/us016——页面 30 次累加太慢）；读数经 adc 模块 API（`adc_get(ADC_1, ADC_Channel_4)`——busy 忙等单点实现在 adc 模块）；页面 ADC 中断（IRQHandler + gCheckADC）改依赖 adc 模块轮询（无 IRQHandler 强符号）；页面 `Get_MQ135_DO_value`/`MQ_DO` 宏（LM393 阈值比较）**不声明 DO 角色**（mq2 同策略——阈值由模块可调电阻控制，需数字量自行经 GPIO 输入读，notes 说明）；**notes 写明与 mq2 的通道方案差异**（mq2=MEM0 薄封装共读、本件=MEM4 独立通道；两者同选不撞 PA24/PB20）与 **MQ 系"相对值非 ppm 精标 + 预热"限制**（MQ-135 对氨气/硫化物/苯系/烟雾灵敏，读数随加热/环境/老化漂移，真实 ppm 需标准气体标定；上电预热几分钟级）。角色 id `MQ135_AO_CH4`（尾 `_CH<N>` 推导 MEM 索引，ir_distance 先例） |
| `mq5` | sensor--mq-5-sensor.md | ADC 模拟量（AO 输出，电压 → 百分比） | 无新 GPIO 实例——ADC12_0 **sequence 开 MEM5**（**endAdd 4→5**、`adcMem5chansel=CHAN_5`、`adcPin5=PB24`） | 同 mq135 **独立 MEM 模式**（批量同构照抄 mq135 工单，差异仅在页面 ADC 倍数/注释与 wordlist 名称）；API = `mq5_init` + `mq5_read_percent`（4095/100 原式、5 次快平均、`adc_get(ADC_1, ADC_Channel_5)`）；页面 ADC 中断改轮询；页面 `Get_MQ5_DO_value` 不声明 DO 角色；默认 PB24（A0_5——其余候选 PA14 板载 LED2+15k 负载不适合作 ADC 模拟输入（board json 注明"PWM 输出时 LED 微亮"，模拟输入会被 15k 分流）；PA22 的 DEBUG_UART RX/HUIDU L1/NRF IRQ/TTP224 OUT1 与气体检测的巡线巡检车/无线气体站/触摸面板环境站更常同框）——与 STEP_MOTOR RST2/SR04 TRIG/HC05 KEY/AT24C02 SCL 重叠（4→5）；notes 同 mq135 模板（通道方案差异 + MQ 系相对值/预热；MQ-5 对丁烷/丙烷/甲烷/天然气灵敏）。角色 id `MQ5_AO_CH5` |
| `sgp30` | sensor--sgp30-gas-sensor.md | 软 I2C 位操作（2 GPIO，SDA 方向运行时切换） | 新 GPIO 实例 `SGP30`/SCL+SDA（照 AHT10/SHT30 先例，不占硬件 I2C 外设） | API = `sgp30_init`（0x2003 初始化空气特征基准——页面 SGP30_Init 语义；上电需 15s 左右预热，预热期 CO2=400ppm、TVOC=0ppb 恒定——初始化判定（读直到 TVOC≠0 且 CO2≠400）归生成骨架/调用方循环，notes 说明）+ `sgp30_read(uint16_t *tvoc_ppb, uint16_t *co2_ppm)`（**先发 0x2008 测量命令**（页面写命令含 delay_ms(100) 覆盖器件测量时长）+ 读 6 字节回包（CO2 高/低 + CRC + TVOC 高/低 + CRC）；**CRC8 器件正确性修正**：SGP30 数据手册要求 CRC8（多项式 0x31、初值 0xFF，同 SHT30/AGS10 系）——页面实现缺 CRC 校验且只读 5 字节（漏 TVOC CRC 字节、`crc = crc` 读回即弃）→ 按 ir_remote 反码校验修正先例补上：读满 6 字节 + 两组 CRC8 校验（**器件正确性修正，非页面语义变化**，notes 记录）；0=成功；1/2/3 = 写命令地址/命令字节应答失败（页面原式无应答检查，按 sht30 风格补）；4 = 读地址应答失败；5 = CRC 校验失败；尺寸换算按页面（CO2 = 高 16 位、TVOC = 低 16 位）；软 I2C 原语静态化（照 SHT30：半周期 5us ≈ 100kHz 级，页面原值；SGP30 规格 ≤400kHz）；默认 SCL=PA18 / SDA=PB9——与 DC_MOTOR AIN2/AIN1（双电机）、MAX7219 CLK/DIN（大数字显示）、RC522 RST（读卡门禁）重叠：气体传感与运动控制/读卡门禁不同框、同选概率最低（刻意不叠温湿度（AHT10 PB6/PB7、DHT11 PB7、DS18B20 PA7、SHT30 PA28/PA31）、光照（PA12/PA13）、OLED 显示（PB2/PB3）、语音（PB19/PB20）、按键（PA2、PA22-27）、报警（PA15）、无线（PA8/PA9/PA23/PA24）、批次 5 八脚——环境站常见搭配），同选时经引脚绑定消解 |
| `ags10` | sensor--ags10-harmful-gas-sensor.md | 软 I2C 位操作（2 GPIO，SDA 方向运行时切换） | 新 GPIO 实例 `AGS10`/SCL+SDA（同先例） | API = `ags10_init`（**空实现占位**——AGS10 无独立初始化序列（页面演示直接读），占位保持 API 一致，mlx90614/at24c02 先例）+ `ags10_read(uint32_t *voc_ppb)`（写地址 0x34 + 寄存器 0x00 → 读地址 0x35 应答重试 → 5 字节回包 = 状态 + TVOC 24bit（data[1..3]）+ CRC（data[4]，`Calc_CRC8(data,4)` 页面原式——初值 0xFF/多项式 0x31 自包含）；**上游缺陷记录**：① 页面读地址重试 `while((WaitAck()==1) && (timeout >= 50))` 条件写反（应为 `timeout < 50`——原式循环一次即退、超时分支 `return 3` 永不触发），按函数注释「等读地址应答 ≤50×1ms、超时返回 3」语义修正（ir_remote/nrf24l01 上游缺陷先例，notes）；② 页面返回值 = TVOC 值/错误码 1-4 混用（TVOC=1 ppb 语义冲突）→ 出参+状态（mlx90614 先例：失败返回 1/2/3/4 = 页面失败码（通信失败/发送失败/等待超时/校验失败），成功返回 0 且 VOC 经出参带回）；软 I2C 原语族（`AGS10_IIC_Start`/`_Stop`/`_Send_Nack`/`_Send_Ack`/`_I2C_WaitAck`/`_Send_Byte`/`_Read_Byte`）收敛为模块内静态（页面 I2C 原语族收敛，照 SHT30）；页面规格「接口速率 ≤15kHz」与页面代码时序（delay_1us(5) ≈ 100kHz）不一致——按页面代码实现、notes 注明（如真机通信异常按 spec 调慢半周期宏）；Calc_CRC8 自包含保留为模块内 static；默认 SCL=PB18 / SDA=PA14——与 DC_MOTOR BIN1（双电机）、MAX7219 CS（大数字显示）、DCC_100_PWM2（step_motor 步进脉冲——风机排烟联动）、WS2812 IN（灯带指示）、RC522 SCK（读卡门禁）重叠：同上（运动控制/读卡/灯带与气体检测低频同框、同选概率最低；避让原则同 sgp30），同选时经引脚绑定消解；与同批默认（PA18/PB9/PB20/PB24）不撞 |

### 默认脚与重叠全景（2026-09-08 定稿）

四件默认 = **PB20（mq135，A0_6/MEM4-CH6）、PB24（mq5，A0_5/MEM5-CH5）、PA18/PB9（sgp30）、PB18/PA14（ags10）**——全部与既有默认重叠（同选概率最低者）、四件互不相撞（多气体检测器 = MQ-135/MQ-5/SGP30/AGS10 最多见组合，默认即不撞）。

- 与既有默认重叠计数（更新 test_pin_bindings.py 刻意重叠表）：PB20 2→3、PB24 4→5、PA18 3→4、PB9 2→3、PB18 2→3、PA14 3→4。
- 与批次 5 八脚（PA16/PA17/PA23/PA24/PA9/PA8/PB24/PB8）：仅 mq5 的 PB24 不可避免（A0_5 是剩余 ADC 通道中「同选概率最低」者；PA22 的伙伴含 DEBUG_UART RX/HUIDU L1/NRF IRQ/TTP224 OUT1——与气体检测的巡线巡检车/无线气体站/触摸面板环境站同框概率更高；PA14 板载 LED2+15k 负载不适合作 ADC 模拟输入）；sgp30（PA18/PB9）、ags10（PB18/PA14）、mq135（PB20）均不撞。mq135 的 PB20 与 SYN6288 TX（语音报警播报）重叠——气体+语音报警为正相关组合但同选概率计最低项（其余 ADC 候选更差），同选经引脚绑定消解（notes 说明）。
- 软 I2C × 硬件 I2C 同脚（PA0/PA1 = I2C_0 外设脚）物理冲突分组：本批 sgp30/ags10 刻意**不叠** PA0/PA1（批次 5 实测调整先例）。
- **气体类与温湿度/显示/报警件刻意错开**（与 ds18b20 选型口诀同源）：温湿度（AHT10 PB6/PB7、DHT11 PB7、DS18B20 PA7、SHT30 PA28/PA31）、光照（PA12/PA13）、OLED（PB2/PB3）、语音（PB19/PB20）、按键（PA2、PA22-27 触摸）、报警（PA15）、无线/视觉（PA8/PA9/PA23/PA24）全部不叠——气体检测器标配=温湿度+显示+蜂鸣/灯+键盘（环境站常见组合），同选概率最高，避免叠加；车类（双电机/舵机/步进）、读卡门禁、大数字显示（MAX7219）、灯带（WS2812）与气体检测低频同框，作为重叠对象。

### 网盘依赖（本批无）

本批四件页内源码完整（v7 审计通过）。例外项随 notes 记录、不阻塞：全部未上板（ADC 换算/软 I2C 时序/CRC 校验真机验证留后续）。

## 测试决策

照批次 1-6 先例逐件：

- `tests/test_pins.py`：
  - `MSPM0_DEFAULT_MAP` 增映射 4 条（sgp30 SCL/SDA、ags10 SCL/SDA 四组 GPIO 角色；mq135/mq5 的 adc 角色无 GPIO 组/外设字段落点，由 test_pin_bindings 落点唯一性覆盖——us016 先例）；
  - `test_module_code_has_no_pin_literals` 豁免元组 `("adc","us016","ir_distance","mq2")` 增 `"mq135","mq5"`（ADC_Channel_N 为 API 对偶枚举）；
- `tests/test_pin_bindings.py` 刻意重叠表更新（PB20 2→3、PB24 4→5、PA18 3→4、PB9 2→3、PB18 2→3、PA14 3→4，注释补新件）；
- `tests/test_syscfg_prune.py` 增 SGP30/AGS10 实例与 ADC12_0 新消费方（mq135/mq5）保留/裁剪断言；
- 新增 `tests/test_module_mq135.py` / `test_module_mq5.py` / `test_module_sgp30.py` / `test_module_ags10.py`：manifest 结构（仅 mspm0 + 依赖）+ mspm0 单选生成（syscfg 含实例/通道 + 模块文件落盘 + main.c 调 init/服务函数过静态门禁）；
- **旧断言全量同步**（ADC 换通道）：`test_module_ir_distance.py`、`test_module_joystick.py`、`test_module_mq2.py`、`test_module_adc.py` 的 endAdd/adcMem/adcPin 断言随母版演进逐一同步（endAdd 3→4（mq135）→5（mq5）；adc 模块注释与 test_module_adc 的 mspm0 侧事实同步）；`adc_mspm0.c/.h` 的 `adc_get` 通道守卫 `> ADC_Channel_3` 扩展为 `> ADC_Channel_5`（MEM4/5 加入共享 API——data 所有权注释同步）；
- **关键源码守卫**（防公式/时序走样，ir_remote_tx `burst_cycle_formula_guard` / mq2 公式守卫先例）：
  - mq135：百分比公式守卫（`4095`/`100.0f`、`ADC_Channel_4`）、无 IRQHandler 守卫（`ADC12_0_INST_IRQHandler`/`gCheckADC` 不得出现）、notes 含「相对值」「ppm」「共读/独立通道差异」；
  - mq5：同上（`ADC_Channel_5` 差异）+ notes 同款守卫；
  - sgp30：命令常量守卫（`0x2003`/`0x2008`）、CRC8 原式守卫（`0x31`/`0xFF`）、**读满 6 字节 + 两组 CRC 校验守卫**（页面漏 TVOC CRC 字节已修正——防回潮）、双出参守卫（`tvoc_ppb`/`co2_ppm`）；
  - ags10：CRC8 守卫（`0x31`/`0xFF`）、**重试条件守卫**（`timeout < 50` 修正写反缺陷——防回潮）、出参+状态守卫（`voc_ppb` 出参、页面 1-4 失败码语义保留）。
- 编译级验收：复制 `run_joystick_matrix.py` 改 slug（四件各一，放 .scratch/wiki-modules-batch7/），gmake 真编译（`C:/ti/ccs2050`）0 error 硬门槛、模块自身 warning 0；结果回写 manifest verified/notes。

## 范围外

- stm32 平台条目、上板真机验证（真机留后续，notes 注明）、新 ADC/TIMER/硬件 I2C 外设实例（本批 ADC12_0 加 MEM4/MEM5，其 GPIO 实例照旧）。
- 正文内嵌段落（行拆散版）不作为提炼源。
- MQ-135/MQ-5 DO 数字量阈值读取（LM393 阈值由模块可调电阻控制，页面 DO 宏/函数未用于演示——同 mq2 策略不声明，需要时经 GPIO 输入自读）、ppm 级精确标定（MQ 系为相对值，需标准气体标定；notes 说明）。
- SGP30 基线读/写（0x2015 get_baseline / 0x2013 set_baseline——页面未实现）、湿度补偿（0x2061 set_humidity——页面未实现）、软复位（0x0006——页面未实现）、自检（0x2032 measure_test——页面未实现）——页面仅 0x2003/0x2008 通路，不实现（notes 说明）；预热判定（上电 15s，CO2=400/TVOC=0 恒定）归生成骨架/调用方（notes 说明）。
- AGS10 预热 ≥120s 等待、寄存器 0x01-0x03 电压/温度校准参数读取（页面未实现）、I2C ≤15kHz spec 时序（按页面代码 5us，notes 注明）。
- 后续批次地图（另立工单）：7b ADC 模拟量薄封装群（ms1100、gp2y1014au、s12sd、rain、soil、photoresistance、flame——ADC 通道按本批独立 MEM 模式顺延 MEM6+）；7c GPIO 薄封装群（human-body-infrared、microwave-doppler）；7d 杂项（l298n、jy61p、open-mv4、sht20、ms5611、mq-3/4/6/7/8/9 同构快补）；8 = 彩屏线（需你下载网盘厂家例程后再开工：0.96/1.3/1.47/1.69/1.28 圆屏/1.8 触摸 + 0.96 SPI 单色，链接在 sources/materials/lckfb-地猛星移植手册/网盘索引.md）。

## 补充说明

- 审计脚本 `.scratch/wiki-materials/audit_v7.py` 可复跑；本批四件均在 v7 全自洽清单内。
- 工单：`issues/01-module-mq135.md` → 02 mq5 → 03 sgp30 → 04 ags10（互相独立，可并行；实施按简→繁：mq135（独立 MEM 打样 + adc 模块扩展）→ mq5（同构照抄）→ sgp30（软 I2C + CRC 补齐）→ ags10（软 I2C + 缺陷修正））。
- 完成后：全量测试套件 + 批次 1-7 全部 27 件 code-review 收尾 + CONTEXT.md 平台行补录 + 中文提交（.githooks/commit-msg 强制中文；.ps1 若新增按 UTF-8 with BOM 存）。
- 词表预算：四件入库后默认词表 wire 实测将超 WORDLIST_PROMPT_BYTES 5400（批次 6 后 5201/上限 5234，余 33B）——按批次 5/6 先例实测后上调预算并同步 budget.py 注释与全文预算边界（结构测试红线，见 tests/test_llm.py 最坏形态）。
