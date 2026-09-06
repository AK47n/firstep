# 06 — ags10 有害气体传感器（软 I2C 总线件 + CRC8，手册 sensor--ags10-harmful-gas-sensor.md）— 全批缺陷最重页

**要做什么：** 模块库 `ags10` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面「代码块」提炼 AGS10 TVOC 驱动为纯驱动切片（软 I2C：2 GPIO + SDA 方向切换；不占硬件 I2C/TIMER），API 与 mspm0 版完全对齐——`ags10_init()`（空实现占位——AGS10 无独立初始化序列，引脚配置由 init 完成；预热 ≥120s 归调用方）+ `ags10_read(uint32_t *voc_ppb)`（写寄存器 0x00（地址 0x34）→ 读地址 0x35 应答重试 ≤50×1ms → 5 字节回包 = 状态 + TVOC 24bit + CRC8 → CRC 校验 → TVOC = (d1<<16)|(d2<<8)|d3 ppb；0=成功/1=通信失败/2=发送失败/3=等待超时/4=校验失败）。

**关键事实（已取证，开工前已读原页，行号以 md 文件为准——sensor--ags10-harmful-gas-sensor.md；详见 %TEMP%\batch2-facts.md 第 6 节）：**
- 页面 = **F1 标准库**（stm32f10x.h + RCC_APB2PeriphClockCmd；OD+IPU+SetBits 拉高）。来源：采购 `https://item.taobao.com/item.htm?spm=a21n57.1.0.0.148e523cqcVeUq&id=709434114260&ns=1&abbucket=8#detail`（AGS10有害气体传感器——**本页无资料下载段**）+ 成功案例 `https://pan.baidu.com/s/1oBG1eHMyNNrstObdw1kDUg?pwd=vhxz`。
- 规格：3.0-6.0V、典型 75mW、**采样周期 ≥2s**、**接口速率 I2C 从机模式（≤15kHz）**、**预热 ≥120s**、0~99999ppb、25℃/50%RH 典型精度 25% 读数、标准测试气体乙醇、15×10.6mm；I2C 物理接口 1kΩ～10kΩ 上拉至 VDD；「SCL上电必须保持高电平直到进行IIC通信开始」；「只能允许一个主机设备出现在总线上」；「读取TVOC数据的步骤：」后内容为空（L54-55，疑原为图片）。
- 代码块：bsp_ags10.c（L64-305：ags10_gpio_init L87（OD+SetBits 拉高）/AGS10_IIC_Start L101（**delay_1us(5)**）/AGS10_IIC_Stop L114/AGS10_IIC_Send_Nack L126（SDA(0)→SDA(1) 冗余二次写）/AGS10_IIC_Send_Ack L139（SDA(1)→SDA(0) 冗余二次写）/AGS10_I2C_WaitAck L159（5us）/AGS10_IIC_Send_Byte L191（**delay_1us(1)**）/AGS10_IIC_Read_Byte L210/Calc_CRC8 L236（0x31/0xFF 原式）/**ags10_read L262-305（uint32_t 主返回 = TVOC 值或错误码 1/2/3/4——混用；L280 `while((AGS10_I2C_WaitAck() == 1) && (timeout >= 50))`——**条件写反致命缺陷**：首轮后 timeout=1、`timeout >= 50` 恒假 → 循环一次即退、L283 `if(timeout >= 50) return 3` 永不触发**；0x34 写/0x35 读硬编码常量；5B 回包前 4 ACK 末字节 Send_Nack；CRC 覆盖 data[0..3]**）**；bsp_ags10.h（L310-358：RCC_AGS10=GPIOB、PORT=GPIOB、**GPIO_SDA=Pin_8/GPIO_SCL=Pin_9（页面默认 SDA=PB8/SCL=PB9）**）；main（L382-401：ags10_gpio_init → printf("Start") → while(1){printf("TVOC = %d ppb", ags10_read()); delay_1ms(1000)}——**未等预热 ≥120s 且 1s 采样 <2s 规格**）。
- **页面缺陷清单（全批最重，全部 notes+守卫）**：① **读地址重试条件写反（致命）**：L280 `(timeout >= 50)` 应为 `timeout < 50`——循环一次即退、超时分支 return 3 永不触发（与函数注释「3：等待超时」矛盾）→ 修正（mspm0 版已同——ir_remote/nrf24l01 上游缺陷先例）；② **返回码与值混用**：ags10_read 主返回 = TVOC 或错误码 1-4（TVOC=1ppb 与「通信失败」不可分）→ 出参 + 状态（mlx90614 先例，mspm0 已同）；③ **delay_1us/delay_1ms 不存在**（ml_delay.h 仅 delay_us/ms/s——页面三处用法改写）；④ **规格 ≤15kHz vs 代码 5us 半周期 ≈100kHz 矛盾**（差 ~7 倍——按页面代码实现，真机通信异常时调慢 SCL 半周期（唯一时序宏点——mspm0 notes 同判）；⑤ 注释掉的调试 printf（Check failed——不落）；⑥ char ack 死变量；⑦ Send_Nack/Ack 冗余二次写（末值正确——页面原式保留）；⑧ main 未等预热 ≥120s + 1s 采样 <2s（演示——不落，预热归调用方 notes）；⑨ 状态字 data[0] 未使用（页面未说明状态位——保留读入不检查）。
- mspm0 版（对齐目标）：ags10.c/.h 见库内（ags10_init 空 + ags10_read(uint32_t*) 0/1/2/3/4；AGS10_ADDR 0x1A/REG_TVOC 0x00/RETRY_MAX 50；CRC8 静态 0x31/0xFF；`timeout < AGS10_RETRY_MAX` 修正；页面 0x34/0x35 脚本化为 (AGS10_ADDR<<1)|0/1）。

**换算实现**：引脚 gpio_init(OUT_OD)（页面原式）+ init 两脚置高（页面 SetBits）；原语族 ags10_iic_*（SDA_OUT=OD、SDA_IN=IU、SDA_GET=gpio_get、SDA/SCL=gpio_set；5us 半周期——页面 delay_1us(5) → delay_us(5)；Send_Nack/Send_Ack 拆两函数按页面原式保留）；ags10_crc8 静态（0x31/0xFF）；API = ags10_init（空占位——无独立初始化序列，引脚配置由 init 完成（页面 ags10_gpio_init 合并——OD+拉高）；预热 ≥120s 归调用方）+ ags10_read（写 0x34+0x00 → 读 0x35 重试 `timeout < 50`（缺陷①修正）→ 5B → CRC 校验（失败 4）→ TVOC 出参 24bit；0=成功/1=通信失败/2=发送失败/3=等待超时/4=校验失败——页面失败码语义）；NULL→0；零寄存器级/标准库调用、零 ml_i2c。

**引脚与默认脚（同选概率最低推理——六件共总线）：**
- pins：`AGS10_SCL`（i2c_scl，default **PA6**，macros `[AGS10_SCL_GPIO, AGS10_SCL_PIN]`）、`AGS10_SDA`（i2c_sda，default **PA7**，macros `[AGS10_SDA_GPIO, AGS10_SDA_PIN]`）。
- pin_config.h 宏段（已随工单 01 落位）：AGS10_SCL_GPIO=GPIO_A/AGS10_SCL_PIN=Pin_6/AGS10_SDA_GPIO=GPIO_A/AGS10_SDA_PIN=Pin_7。
- 默认脚推理：气体检测与温湿度/光照/EEPROM 共挂 PA6/PA7（地址 0x1A 与其它五件全异——空气质量站（气体+温湿度+光照+记录）合法共挂；**刻意不叠 mspm0 侧 ags10 默认 PB18/PA14 同框组合**——stm32 侧共总线设计）；与 motor MOTOR_A_DIR/DIR2（电机方向）重叠：有害气体传感与「带电机方向的小车运动控制」不同框、同选概率最低；**页面默认 SDA=PB8/SCL=PB9 不采用**（= 母版 OLED 段）；同选经引脚绑定消解。

**被谁阻塞：** 无——可立即开始（全批最重件）。

**状态：** resolved

**实施清单：**
- [x] `library/modules/ags10/code/ags10_stm32.c/.h`（照 aht10_stm32 样式；5us 半周期 + CRC8 0x31/0xFF + `timeout < AGS10_RETRY_MAX` 修正 + 出参+状态码 + NULL→0；页面缺陷注释全记录——含致命①② 与 delay_1us/delay_1ms 改写；Send_Nack/Send_Ack 拆两函数按页面原式保留）
- [x] `manifest.json` platforms 增 stm32（files/verified false→**true**（矩阵后）/pins 如上/kit=AGS10 有害气体传感器模块（5Pin I2C，地址 0x1A）/source_url wiki 原页/notes 手册路径+原页+网盘（成功案例）+采购+缺陷清单（9 条）+规格分歧（≤15kHz）+默认脚推理+未上板+矩阵记录）
- [x] 测试 `tests/test_module_ags10.py`（照模板：形状 + 宏存在 + stm32 单选生成 + mspm0 零改动 + 守卫（`timeout < AGS10_RETRY_MAX` 修正（防回潮条件写反）/出参+状态码（无 uint32_t 主返回混用）/CRC8 0x31/0xFF/TVOC 24bit 拼装/失败码 1-4/无 delay_1us delay_1ms/无 printf 残留/无 ml_i2c/标准库）——26 组合跑绿）
- [x] `tests/test_pins.py` STM32_MACRO_VALUES 补 AGS10 4 宏；`tests/test_default_layout.py` 白名单 PA6/PA7 组加入 ags10 两角色（**六件全齐收口**）
- [x] 编译矩阵 → UV4 **exit 0，0 error、0 module warning** → verified=true 回写
- [x] 中文提交 → resolved → 结论回填

**验收记录：**
- 矩阵 PASS：UV4 V5.06u7 `-j0 -r -b` exit 0，`0 Error(s), 0 Warning(s)`；产物 Program Size: Code=2240。
- 换算要点回填：页面 OD+IPU 原式 → ml_gpio OUT_OD/IU（init 两脚置高 = 页面 SetBits——「SCL上电必须保持高电平」要求）；页面 delay_1us(5)/delay_1ms(1) → delay_us(5)/delay_ms(1)（库内不存在——缺陷③）；Send_Nack/Send_Ack 拆两函数（页面原式冗余二次写保留——缺陷⑦）；CRC8 0x31/0xFF 覆盖 data[0..3]（页面原式、静态化）；地址硬编码 0x34/0x35 → (AGS10_ADDR<<1)|0/1 脚本化（0x1A 7bit）。
- **页面致命缺陷回填（全批最重）**：① 读地址重试条件写反 `(timeout >= 50)`（L280——循环一次即退、return 3 永不触发，与函数注释矛盾）→ `timeout < AGS10_RETRY_MAX` 修正；② 返回码与 TVOC 值混用（TVOC=1ppb 与「通信失败」不可分）→ 出参 + 状态码（mlx90614 先例）；③ delay_1us/delay_1ms 改写；④ 规格 ≤15kHz vs 代码 100kHz（按代码 + 唯一时序宏点）；⑤ 注释掉 printf（不落）；⑥ char ack 死变量收敛；⑦ 冗余二次写保留原式；⑧ main 未等预热/1s 采样 <2s（演示不落，预热归调用方）；⑨ 状态字 data[0] 读入不检查（页面未说明语义）。
- 测试：test_module_ags10 7 passed（双平台形状 + 宏存在 + stm32/mspm0 单选生成 + 代码守卫）；test_pins/test_default_layout 26 passed 组合跑（**六件白名单收口：PA6/PA7 七角色组全登记**）。
- 词表：ags10 已挂接（mspm0 批），零补录；依赖 ["delay"] 零改动。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
