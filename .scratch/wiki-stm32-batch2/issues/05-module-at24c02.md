# 05 — at24c02 EEPROM 存储器（软 I2C 总线件·读写件，手册 control--at24c02-eeprom-memory.md）

**要做什么：** 模块库 `at24c02` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面「代码块」提炼 AT24C02 EEPROM 驱动为纯驱动切片（软 I2C：2 GPIO + SDA 方向切换，不占硬件 I2C/TIMER），API 与 mspm0 版完全对齐——`at24c02_init()`（空占位）+ `at24c02_write_byte(addr,data)`（字节写，void 页面原式）+ `at24c02_read_byte(addr)`（随机读，无应答返回 0xFF——页面同款）+ `at24c02_wait_write_done()`（~5ms 写周期等待）+ `at24c02_write_page(addr,data,len)`（16 字节页写、跨页拒收；0=成功/1=参数错/2=无应答）+ `at24c02_read_block(addr,buf,len)`（连续读；0=成功/1=参数错/2=无应答）。

**关键事实（已取证，开工前已读原页，行号以 md 文件为准——control--at24c02-eeprom-memory.md；详见 %TEMP%\batch2-facts.md 第 5 节）：**
- 页面 = **F1 标准库**（stm32f10x.h + RCC_APB2PeriphClockCmd + Mode_Out_OD/IPU + WriteBit/ReadInputDataBit）。来源：采购 `https://detail.tmall.com/item.htm?abbucket=0&id=698591628199&ns=1&spm=a21n57.1.0.0.7edf523co7QMUt`（EEPROM存储模块器AT24C02/04/08/16/32/64/128/256可选I2C接口——**本页无「资料下载链接」段**）+ 成功案例 `https://pan.baidu.com/s/1-X1eg-Ck0jsKpvPGePH0VQ?pwd=z9zh`。
- 规格：1.8-5.5V、最大 3mA、IIC、2048 位（256 字节）；**时钟 5V 时最大 1000kHz、其余 400kHz**（软 I2C ~100kHz 低于规格裕量足）；7 位地址高 4 位固定 1010、低 3 位 A2A1A0、一条总线可挂 8 枚；字节写/页写（**页大小 16 字节**、附加字节 P=15）；「接收到 P+1 字节数据和停止信号后…启动内部写周期」（期间不响应）；当前地址读/随机读/连续读（256 边界翻转）；「23=8」= 上标丢失的 2^3=8。
- 代码块：bsp_at24c02.c（L58-300：**地址宏 L75-77（SLAVE ADDRESS+W为0xA0/R为0xA1 + `AT24C02_ADDRESS_READ 0xA0`/`AT24C02_ADDRESS_WRITE 0xA1`——**宏名 READ/WRITE 与值语义颠倒**，功能因调用「宏名反着用」而侥幸正确）**、AT24C02_GPIO_Init L87（OD——**无 SetBits 拉高**）/IIC_Start L106（5us×4）/IIC_Stop L129/IIC_Send_Ack L150/I2C_WaitAck L172/Send_Byte L210（1/5/5）/Read_Byte L236（5/5/5）/AT24C02_WriteByte L265（void——三次 WaitAck 结果全丢弃）/AT24C02_ReadByte L285-300（伪写定位→重 Start+读 0xA1→NACK→Stop，同样无应答检查））；bsp_at24c02.h（L305-354：RCC_AT24C02=GPIOB、PORT=GPIOB、**GPIO_SDA=Pin_8/GPIO_SCL=Pin_9（页面默认 SDA=PB8/SCL=PB9）**）；main（L379-419：WriteByte(0,48)+delay_ms(5) → WriteByte(8,66)（**注释 L395「向8地址写入数据48」应为 66——缺陷**）+delay_ms(5) → ReadByte(0)/ReadByte(8) → printf）。
- **页面缺陷清单（全部 notes+守卫）**：① **地址宏名颠倒（主缺陷）**：页面 L75-77 注释「+W为0xA0/+R为0xA1」、宏 `AT24C02_ADDRESS_READ 0xA0`/`AT24C02_ADDRESS_WRITE 0xA1`——宏名与语义互换（功能因调用名称恰好反着用而正确）→ `AT24C02_ADDR_WRITE (0x50<<1)=0xA0`/`ADDR_READ (0x50<<1|1)=0xA1` 纠正命名、值保留页面原式；② **读写路径应答全丢弃、无错误返回**（WriteByte void 页面原式保留——mspm0 同款；read_byte 无应答返回 0xFF 页面同款——与合法 0xFF 不可分，调用方先写后读验证；write_page/read_block 补 2=无应答返回）；③ 注释 48/66 不符（L395——main 演示不落库）；④ main `%d` 打 unsigned char（演示不落）；⑤ **写周期 5ms 未封装**（main 裸 delay_ms(5)）→ at24c02_wait_write_done 封装；⑥ **页写/连续读正文有述、代码未实现**（L42/48 vs 仅字节读写）→ 按正文补齐（跨页边界/len>16 拒收、连续读 256 边界翻转）；⑤' GPIO_Init 无 SetBits（页面原样——总线空闲电平由首次事务拉起，照 mspm0 版）。
- 原语时序：页面 5us 半周期 → **mspm0 版归一 2us（aht10 同款——「页面 delay_us(1)/5/5 混合半周期已统一为 2us」）**；stm32 版同归一（≈100kHz 级，400kHz 规格裕量足）。
- mspm0 版（对齐目标）：at24c02.c/.h 见库内（init 空/write_byte/read_byte/wait_write_done/write_page/read_block；AT24C02_ADDR 0x50、WRITE 0xA0、READ 0xA1、SIZE 256、PAGE_SIZE 16、WRITE_CYCLE_MS 5；WP 写保护由硬件接线管理 VCC 读保护/GND 可写——驱动不控制）。

**换算实现**：引脚 gpio_init(OUT_OD)（页面原式）+ init 两脚置高（总线空闲电平——页面无 SetBits，照 mspm0 版 init 仅占空位、置高由事务序列完成——stm32 版 init 空占位 + 引脚配置由 init 完成（gpio_init + 置高，照 mspm0 版无独立 GPIO_Init）；原语族 at24c02_iic_*（2us 半周期归一，mspm0 同款）；API 全对齐 mspm0（失败码 0/1/2；write_byte/read_byte 页面原式；wait_write_done = delay_ms(5)；write_page 跨页/len>16 拒收；read_block 首字节 ACK 末字节 NACK、连续读 256 边界翻转——len 上限 255）；NULL→0；零寄存器级/标准库调用、零 ml_i2c。

**引脚与默认脚（同选概率最低推理——六件共总线）：**
- pins：`AT24C02_SCL`（i2c_scl，default **PA6**，macros `[AT24C02_SCL_GPIO, AT24C02_SCL_PIN]`）、`AT24C02_SDA`（i2c_sda，default **PA7**，macros `[AT24C02_SDA_GPIO, AT24C02_SDA_PIN]`）。
- pin_config.h 宏段（已随工单 01 落位）：AT24C02_SCL_GPIO=GPIO_A/AT24C02_SCL_PIN=Pin_6/AT24C02_SDA_GPIO=GPIO_A/AT24C02_SDA_PIN=Pin_7。
- 默认脚推理：EEPROM 存储记录与传感件共挂 PA6/PA7（地址 0x50 与其它五件全异——环境记录站（温湿度+光照+EEPROM 掉电参数）合法共挂）；与 motor MOTOR_A_DIR/DIR2（电机方向）重叠：存储记录与「带电机方向的小车运动控制」不同框、同选概率最低（记录类与运动类不同框——mspm0 侧同判）；**页面默认 SDA=PB8/SCL=PB9 不采用**（= 母版 OLED 段）；同选经引脚绑定消解。

**被谁阻塞：** 无——可立即开始（本批 API 面最宽件）。

**状态：** resolved

**实施清单：**
- [x] `library/modules/at24c02/code/at24c02_stm32.c/.h`（照 aht10_stm32 样式；2us 半周期归一 + 地址宏命名纠正（AT24C02_ADDR_WRITE 0xA0/READ 0xA1）+ write_page/read_block 补齐 + wait_write_done + NULL→0；页面缺陷注释全记录——宏名颠倒/应答丢弃/48 66 注释/写周期封装/页写连续读补齐）
- [x] `manifest.json` platforms 增 stm32（files/verified false→**true**（矩阵后）/pins 如上/kit=EEPROM 存储模块 AT24C02（I2C 接口）/source_url wiki 原页/notes 手册路径+原页+网盘（成功案例）+采购+缺陷清单+默认脚推理+未上板+矩阵记录）
- [x] 测试 `tests/test_module_at24c02.py`（照模板：形状 + 宏存在 + stm32 单选生成 + mspm0 零改动 + 守卫（AT24C02_ADDR_WRITE 0xA0/ADDR_READ 0xA1 命名纠正/PAGE_SIZE 16/跨页拒收/read_block 末字节 NACK/wait_write_done 5ms/失败码 1-2/无 printf 残留/无 ml_i2c/标准库）——26 组合跑绿）
- [x] `tests/test_pins.py` STM32_MACRO_VALUES 补 AT24C02 4 宏；`tests/test_default_layout.py` 白名单 PA6/PA7 组加入 at24c02 两角色
- [x] 编译矩阵 → UV4 **exit 0，0 error、0 module warning** → verified=true 回写
- [x] 中文提交 → resolved → 结论回填

**验收记录：**
- 矩阵 PASS：UV4 V5.06u7 `-j0 -r -b` exit 0，`0 Error(s), 0 Warning(s)`；产物 Program Size: Code=2300。
- 换算要点回填：页面 OD+IPU 原式 → ml_gpio OUT_OD/IU（init 两脚置高 = 总线空闲电平——页面无 SetBits，同 BH1750/SHT20 页惯例）；页面 1/5/5 混合半周期 → 归一 2us（aht10 先例——mspm0 版同款，notes 记录页面变体）；页面地址宏名颠倒 → AT24C02_ADDR_WRITE (0x50<<1)=0xA0 / ADDR_READ (0x50<<1|1)=0xA1（值保留页面原式 0xA0/0xA1——功能因调用巧合正确，命名纠正）；WriteByte/ReadByte → write_byte（void 页面原式）/read_byte（0xFF 页面同款——与合法 0xFF 不可分，调用方先写后读验证）；写周期裸 delay_ms(5) → wait_write_done 封装（AT24C02_WRITE_CYCLE_MS=5）；页写/连续读按页面正文补齐（≤16B 页内/跨页拒收；连续读首字节 ACK 末字节 NACK、256 边界翻转）。
- 页面缺陷回填（全部 notes + 守卫）：① 地址宏名颠倒（主缺陷）；② 读写应答全丢弃（write_page/read_block 补失败码 2；write_byte/read_byte 页面原式保留）；③ 注释 48/66 不符（演示不落）；④ %d 打 unsigned char（演示不落）；⑤ 写周期 5ms 未封装 → wait_write_done；⑥ 页写/连续读代码未实现 → 补齐。
- 测试：test_module_at24c02 7 passed（双平台形状 + 宏存在 + stm32/mspm0 单选生成 + 代码守卫）；test_pins/test_default_layout 26 passed 组合跑。
- 词表：at24c02 已挂接（mspm0 批），零补录；依赖 ["delay"] 零改动。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
