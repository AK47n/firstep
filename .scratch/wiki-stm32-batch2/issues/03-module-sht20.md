# 03 — sht20 温湿度传感器（软 I2C 总线件，手册 sensor--sht20-temp-humi-sensor.md）

**要做什么：** 模块库 `sht20` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面「代码块」提炼 SHT20（SHT2x 旧系列）温湿度驱动为纯驱动切片（软 I2C：2 GPIO + SDA 方向切换；低功耗单次测量 no-hold），API 与 mspm0 版完全对齐——`sht20_init()`（空占位）+ `sht20_read(float *t, float *h)`（0xF3 温度/0xF5 湿度两段各：写地址 0x80 → 写命令 → 读地址应答重试 ≤50×2ms → 2B + NACK；raw & 0xFFFC；温度 = raw/65536×175.72−46.85、湿度 = raw/65536×125−6；0=成功/1=温度段失败/2=湿度段失败）。

**关键事实（已取证，开工前已读原页，行号以 md 文件为准——sensor--sht20-temp-humi-sensor.md；详见 %TEMP%\batch2-facts.md 第 3 节）：**
- 页面 = **F1 标准库**（stm32f10x.h + RCC_APB2PeriphClockCmd + Mode_Out_OD/IPU + WriteBit/ReadInputDataBit）。来源：采购 `https://item.taobao.com/item.htm?spm=a21n57.1.0.0.700a523chCfvAP&id=615550651141&ns=1&abbucket=0#detail`（SHT20温湿度传感器模块/数字型温湿度测量模块 I2C通讯小体积模块）+ 资料 `https://pan.baidu.com/s/1HrQkwECvGgQSHvt_RNdLdA`（页面未给提取码）+ 成功案例 `https://pan.baidu.com/s/1LfEC08A8IC3KP0ab5r3MmA?pwd=7070`。
- 规格：2.1-3.6V、0.1-1000uA、±0.3℃/±3%RH、-40~125℃、4 Pin；最长测量 85ms（温 14bit）/29ms（湿 12bit）；**「两个状态位，即 LSB 的后两位在进行物理计算前须置0」**（L68）；**「校验和可以不需要…返回NACK」**（L54——页面明确无 CRC）。
- 代码块：bsp_sht20.c（L80-313：SHT20_GPIO_INIT L96（OD+SetBits）/IIC_Start L117（SCL(0)→SDA(1)→SCL(1)→5us→SDA(0)→5us→SCL(0)）/IIC_Stop L142/IIC_Send_Ack L164/IIC_Wait_Ack L186（SDA_IN→SDA(1)→5us）/IIC_Write L221（2/6/4/4 混合延迟）/IIC_Read L249（5us）/SHT20_Read L277（**注释 L272-273 写 0xE3/0xE5（hold）而代码 L303/307 用 0xf3/0xf5（no-hold）+ 换算 L305/309**））；bsp_sht20.h（L318-366：RCC_SHT20=GPIOB、PORT=GPIOB、**GPIO_SDA=Pin_9/GPIO_SCL=Pin_8（页面默认 SDA=PB9/SCL=PB8）**）；main（L394-414：SHT20_GPIO_INIT → delay_ms(1000) → while(1){SHT20_Read(T_ADDR 0xf3) 温度/SHT20_Read(PH_ADDR 0xf5) 湿度;delay_ms(1000)}）。
- **页面缺陷清单（全部 notes+守卫）**：① **do-while 裸轮询无上限**（L288-293——器件失联死等；内部 WaitAck 单次 10×5us 超时）→ 改 ≤50×2ms 重试（100ms 窗口覆盖 85ms 规格——mspm0 版已同）；② **状态位未掩码（主缺陷）**：正文 L68 要求「物理计算前须置0」而代码 L305/309 未 &0xFFFC → 修正（误差 <0.01℃/0.05%RH）；③ **0xE3/0xE5 vs 0xF3/0xF5 三方矛盾**（正文 L48+注释 L272-273 写 hold 命令、代码+main 宏用 no-hold——采信代码 0xF3/0xF5，notes 记录）；④ 写地址/命令应答失败仅 printf 后继续（L284/286——错误无传播）→ 失败码 1/2 返回；⑤ char ack 死变量/类型宽度 → uint8_t 收敛。
- 原语时序：页面 2-6us 混合变体 → **mspm0 版归一 5us 半周期（sht30 同款）**——stm32 版同归一（≈100kHz，规格 ≤400kHz 裕量足；notes 记录页面变体）。
- mspm0 版（对齐目标）：sht20.c/.h 见库内（init 空占位 + read 出参；SHT20_ADDR 0x40/CMD_TEMP 0xF3/CMD_HUMI 0xF5/RETRY 50×2ms；&0xFFFC 掩码；换算 0.01 系数原式；**无 CRC 按页面取舍**）；**与库内 pca9685（0x40）同址**——notes 提醒（共总线同选冲突须错开）。

**换算实现**：引脚 gpio_init(OUT_OD)（页面原式）+ init 两脚置高（页面 SetBits）；原语族 sht20_iic_*（SDA_OUT=OD、SDA_IN=IU、SDA_GET=gpio_get、SDA/SCL=gpio_set；5us 半周期归一）；sht20_measure_once 静态（写地址 → 命令 → 应答重试 ≤50×2ms → 2B+NACK → &0xFFFC 掩码；1/2/3 页面失败码段）；API = sht20_init（空实现占位——单次模式无预置命令，mspm0 先例）+ sht20_read（温度段 0xF3 → 失败 1；湿度段 0xF5 → 失败 2；出参判空用 0）；零寄存器级/标准库调用、零 ml_i2c。

**引脚与默认脚（同选概率最低推理——六件共总线）：**
- pins：`SHT20_SCL`（i2c_scl，default **PA6**，macros `[SHT20_SCL_GPIO, SHT20_SCL_PIN]`）、`SHT20_SDA`（i2c_sda，default **PA7**，macros `[SHT20_SDA_GPIO, SHT20_SDA_PIN]`）。
- pin_config.h 宏段（已随工单 01 落位）：SHT20_SCL_GPIO=GPIO_A/SHT20_SCL_PIN=Pin_6/SHT20_SDA_GPIO=GPIO_A/SHT20_SDA_PIN=Pin_7。
- 默认脚推理：温湿度与光照/气体/EEPROM 共挂 PA6/PA7（地址 0x40 与其它五件全异——环境站合法共挂；**注意与 pca9685 同址 0x40**：同总线双选 = 寻址冲突，须错开总线或改 pca9685 地址——notes 提醒）；与 motor MOTOR_A_DIR/DIR2（电机方向）重叠：温湿度与「带电机方向的小车运动控制」不同框、同选概率最低；**页面默认 SDA=PB9/SCL=PB8 不采用**（= 母版 OLED 段）；同选经引脚绑定消解。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/sht20/code/sht20_stm32.c/.h`（照 aht10_stm32 样式；5us 半周期归一 + &0xFFFC 掩码 + ≤50×2ms 重试 + 失败码 1/2/3 + NULL→0；页面缺陷注释全记录——裸轮询/掩码/0xE3 0xE5 矛盾/printf 后继续/char 死变量）
- [x] `manifest.json` platforms 增 stm32（files/verified false→**true**（矩阵后）/pins 如上/kit/source_url wiki 原页/notes 手册路径+原页+网盘×2+采购+缺陷清单+同址提醒（pca9685 0x40）+默认脚推理+未上板+矩阵记录）
- [x] 测试 `tests/test_module_sht20.py`（照模板：形状 + 宏存在 + stm32 单选生成 + mspm0 零改动 + 守卫（&0xFFFC 掩码/0xF3 0xF5 命令/RETRY 50×2ms/换算 175.72/46.85/125.0/6.0/无 printf 残留/无 ml_i2c/标准库）——26 组合跑绿）
- [x] `tests/test_pins.py` STM32_MACRO_VALUES 补 SHT20 4 宏；`tests/test_default_layout.py` 白名单 PA6/PA7 组加入 sht20 两角色
- [x] 编译矩阵 → UV4 **exit 0，0 error、0 module warning** → verified=true 回写
- [x] 中文提交 → resolved → 结论回填

**验收记录：**
- 矩阵 PASS：UV4 V5.06u7 `-j0 -r -b` exit 0，`0 Error(s), 0 Warning(s)`；产物 Program Size: Code=3484。
- 换算要点回填：页面 OD+IPU 原式 → ml_gpio OUT_OD/IU（init 两脚置高 = 页面 SetBits）；页面 2-6us 混合半周期 → 归一 5us（sht30 同款——mspm0 版同，notes 记录变体）；页面 SHT20_Read 单值形态 → sht20_measure_once 静态（温度/湿度两段）；页面 do-while 裸轮询 → ≤50×2ms（100ms 窗口覆盖 85ms/29ms）；**状态位 &0xFFFC 掩码修正**（页面正文要求、代码未做；误差 <0.01℃/0.05%RH）；页面注释 0xE3/0xE5（hold）vs 代码 0xF3/0xF5（no-hold）→ 采信代码（mspm0 同）；无 CRC 按页面取舍（末字节 NACK）。
- 测试：test_module_sht20 7 passed（双平台形状 + 宏存在 + stm32/mspm0 单选生成 + 代码守卫）；test_pins/test_default_layout 26 passed 组合跑。
- 词表：sht20 已挂接（mspm0 批），零补录；依赖 ["delay"] 零改动。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
