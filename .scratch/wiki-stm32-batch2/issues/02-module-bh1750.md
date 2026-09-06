# 02 — bh1750 光照强度传感器（软 I2C 总线件，手册 sensor--bh1750-light-intensity-sensor.md）

**要做什么：** 模块库 `bh1750` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面「代码块」提炼 GY-30（BH1750FVI）光照驱动为纯驱动切片（软 I2C：2 GPIO + SDA 方向切换，不占硬件 I2C/TIMER），API 与 mspm0 版完全对齐——`bh1750_init()`（上电 0x01）、`bh1750_start_measure()`（0x10 连续高分辨率；0=成功/1=无应答）、`bh1750_read_lux(float*)`（读地址 0x47 → 2B 高前低后 → /1.2；0=成功/1=无应答）。选中 stm32 生成工程打开即可编译、可调用。

**关键事实（已取证，开工前已读原页，行号以 md 文件为准——sensor--bh1750-light-intensity-sensor.md；详见 %TEMP%\batch2-facts.md 第 2 节）：**
- 页面 = **F1 标准库**（stm32f10x.h + RCC_APB2PeriphClockCmd + Mode_Out_OD/IPU + WriteBit/ReadInputDataBit/SetBits）。模块来源：采购 `https://detail.tmall.com/item.htm?_u=52t4uge534a7&id=598334245306&spm=a1z09.2.0.0.47582e8dxs1caw`（GY30光照传感器模块 数字光强度BH1750FVI光照度）+ 资料 `https://pan.baidu.com/s/13bVmmj0eM22mT8pBusjIyQ?pwd=8889`（提取码 8889）+ 成功案例 `https://pan.baidu.com/s/1N-LECZIUaEdqIZGAVHgKkA?pwd=tnzu`。
- 规格：3-5V、200uA、探测范围 1~65536lx（规格表）/0-65535lx（正文——记录不裁决）、16bit AD、5 Pin；命令 0x01 上电 / 0x10 连续高分辨率（1lx、120ms、「手册推荐」）/ 0x20 单次高分辨率（120ms 后回掉电）；「读取完成之后…除以1.2即可得到光照强度」。
- 代码块：bsp_gy30.c（L72-331：GY30_GPIO_Init L99/IIC_Start L120/IIC_Stop L143/IIC_Send_Ack L164/I2C_WaitAck L186/Send_Byte L225/Read_Byte L251/Single_Write_BH1750 L280（0/1/2 返回）/Multiple_read_BH1750 L299（float；`(hi<<8)+lo` → `/1.2f`）/GY30_Init L327（GPIO_Init + 0x01 上电）+ 死全局 `BUF[8]` L89）；bsp_gy30.h（L336-389：RCC_GY30=RCC_APB2Periph_GPIOB、PORT_GY30=GPIOB、**GPIO_SDA=Pin_8、GPIO_SCL=Pin_9（页面默认 SDA=PB8/SCL=PB9）**、SlaveAddress=0x46（ALT 接地；接电源 0xB8））；main（L414-433：GY30_Init → Single_Write(0x10) → delay_ms(180) → Multiple_read → printf）。
- **页面缺陷清单（全部 notes+守卫）**：① **读路径 WaitAck 丢弃**（Multiple_read L306 读地址应答不检查，无应答仍读）→ bh1750_read_lux 检查并返回 1；② **模板串台**：L93 GY30_GPIO_Init 注释「**MLX90614的引脚初始化**」（红外测温页残留）；③ BUF[8] 死全局非 static；④ 注释块函数名「Single_Write」（缺 _BH1750 后缀）与函数名不符；⑤ 规格 1~65536 vs 正文 0-65535（记录不裁决）；⑥ main 测量等待 180ms 硬编码 → 模块宏 BH1750_MEASURE_DELAY_MS=140（mspm0 同款；≥120ms 推荐值，等待归调用方）。
- 原语时序 = 页面原值 5us 半周期（≈100kHz，BH1750 ≤400kHz 裕量足）；单次测量 → 掉电（连续高分辨率 0x10 会持续转换——main 反复发 0x10 属页面惯性，照 mspm0 版：start_measure 一次 + 等 140ms + read_lux，调用方控制节奏）。
- mspm0 版（对齐目标）：bh1750.h 见库内（init/start_measure/read_lux；BH1750_MEASURE_DELAY_MS 140；地址 0x46 写/0x47 读；/1.2f 原式；读取路径 wait_ack 检查返回 1——页面缺陷①已修正；页面 GY30_/IIC_/Single_Write 菜市场命名收敛）。

**换算实现**：引脚 `gpio_init(BH1750_SCL/SDA_GPIO, …PIN, OUT_OD)`（页面原式 OD；GPIO_SetBits 拉高 = init 时 gpio_set 两脚 1）；原语族 bh1750_iic_*（SDA_OUT=OD、SDA_IN=IU、SDA_GET=gpio_get、SDA/SCL=gpio_set；时序 5us 原值）；bh1750_write_cmd 静态（start→0x46→wait_ack 检查→cmd→wait_ack 检查→stop；0=成功/1=无应答——页面 0/1/2 歧义统一）；API = init/start_measure/read_lux（0=成功/1=无应答）+ BH1750_MEASURE_DELAY_MS 140 宏（等待由调用方）；零寄存器级/标准库调用、零 ml_i2c。

**引脚与默认脚（同选概率最低推理——六件共总线）：**
- pins：`BH1750_SCL`（i2c_scl，default **PA6**，macros `[BH1750_SCL_GPIO, BH1750_SCL_PIN]`）、`BH1750_SDA`（i2c_sda，default **PA7**，macros `[BH1750_SDA_GPIO, BH1750_SDA_PIN]`）。
- pin_config.h 宏段（已随工单 01 落位 24 宏）：BH1750_SCL_GPIO=GPIO_A/BH1750_SCL_PIN=Pin_6/BH1750_SDA_GPIO=GPIO_A/BH1750_SDA_PIN=Pin_7。
- 默认脚推理：**光照与温湿度/气体/存储共挂 PA6/PA7 总线**（地址 0x23 与 0x38/0x40/0x44/0x50/0x1A 全异——环境站（温湿度+光照+EEPROM 记录）合法共挂；刻意不叠 AHT10 类互替总线段——共总线即为同一总线）；与 motor MOTOR_A_DIR/DIR2（电机方向）重叠：光照传感与「带电机方向的小车运动控制」不同框、同选概率最低（刻意不叠显示/声光/输入/串口/无线/USB/SWD）；**页面默认 SDA=PB8/SCL=PB9 不采用**（= 母版 OLED_GPIO 段——光照+OLED 显示同框概率高）；同选经引脚绑定消解。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/bh1750/code/bh1750_stm32.c/.h`（照 aht10_stm32 样式：OD/IU 页面原式 + 5us 时序 + wait_ack 检查 + NULL→0；页面缺陷注释全记录——MLX90614 串台/BUF 死全局/Single_Write 注释缺后缀/规格 65536 分歧/180ms 硬编码 → 140 宏）
- [x] `manifest.json` platforms 增 stm32（files/verified false→**true**（矩阵后）/hardware_bound false/pins 如上/kit=GY30 光照传感器模块（BH1750FVI，ALT 接地地址 0x46）/source_url wiki 原页/notes 手册路径+原页+网盘×2+采购+缺陷清单+默认脚推理+未上板+矩阵记录）
- [x] 测试 `tests/test_module_bh1750.py`（照 test_module_aht10.py 模板：形状（pins i2c_scl/i2c_sda PA6/PA7 四宏）+ 宏存在 + stm32 单选生成 + mspm0 零改动 + 守卫（无 MLX90614 串台/无 BUF 全局/0x10 与 0x01 命令/BH1750_MEASURE_DELAY_MS 140/read_lux wait_ack 检查返回 1/无 ml_i2c/标准库）——26 组合跑绿）
- [x] `tests/test_pins.py` STM32_MACRO_VALUES 补 BH1750 4 宏；`tests/test_default_layout.py` 白名单 PA6/PA7 组加入 bh1750 两角色
- [x] 编译矩阵 `.scratch/wiki-stm32-batch2/matrix/run_bh1750_matrix.py` → UV4 **exit 0，0 error、0 module warning** → verified=true 回写
- [x] 中文提交 → resolved → 结论回填

**验收记录：**
- 矩阵 PASS：UV4 V5.06u7 `-j0 -r -b` exit 0，`0 Error(s), 0 Warning(s)`；产物 Program Size: Code=2640。
- 换算要点回填：页面原式 OD+IPU → ml_gpio OUT_OD/IU（init 时两脚置高 = 页面 GPIO_SetBits 拉高）；时序 5us 半周期原值；页面 Single_Write_BH1750 返回 0/1/2（器件地址错/命令错两失败位）→ 统一 0/1（mspm0 同款收敛——两失败位语义相同）；读路径 I2C_WaitAck 丢弃（页面 L306）→ 检查返回 1（缺陷①）；0x10 由 start_measure 独立暴露（页面散在 main——GY30_Init 只上电）；main 测量等待 180ms → BH1750_MEASURE_DELAY_MS=140 宏（等待归调用方）。
- 页面缺陷回填（全部 notes + 守卫）：① 读路径应答丢弃修正；② MLX90614 注释串台（不落）；③ BUF[8] 死全局 + 注释块函数名缺后缀（不落）；④ 规格表 1~65536 vs 正文 0-65535（记录不裁决）；⑤ 180ms 硬编码 → 140 宏。
- 测试：test_module_bh1750 7 passed（双平台形状 + 宏存在 + stm32/mspm0 单选生成 + 代码守卫）；test_pins/test_default_layout 26 passed 组合跑。
- 词表：bh1750 已挂接（mspm0 批），零补录。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
