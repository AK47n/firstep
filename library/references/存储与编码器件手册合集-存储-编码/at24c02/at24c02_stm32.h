/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《AT24C02-EEPROM存储器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/at24c02-eeprom-memory.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef AT24C02_STM32_H
#define AT24C02_STM32_H

#include <stdint.h>

/* AT24C02 EEPROM 存储器驱动（stm32，纯驱动切片，ADR 0009）：软 I2C 位操作
 * （SCL/SDA 两 GPIO，SDA 方向运行时切换——不占硬件 I2C 外设/TIMER），字节
 * 写/读（页面原式）+ 页写（16 字节页缓冲，跨页边界拒收）+ 连续读 + 写周期
 * 等待（~5ms 走 delay 模块）。API 与 mspm0 版完全对齐（at24c02_init/
 * write_byte/read_byte/wait_write_done/write_page/read_block，同函数名/
 * 同语义/同返回码）。
 * 引脚 = pin_config.h 单源 AT24C02_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN
 * （默认 PA6/PA7——与 motor MOTOR_A_DIR/DIR2 默认重叠：存储记录与「带电机
 * 方向的小车运动控制」不同框、同选概率最低；**六件软 I2C 件默认共挂此总线**
 * （地址 0x38/0x23/0x40/0x44/0x50/0x1A 全异——环境记录站合法共挂；页面
 * 默认 SDA=PB8/SCL=PB9 不采用 = 母版 OLED 段），同选时经引脚绑定消解。
 * 通信协议（AT24C02 数据手册 / 立创移植手册）：7 位器件地址 0x50（A2A1A0 =
 * 000，一条总线可挂 8 枚），8 位写/读 = 0xA0/0xA1（**页面宏名颠倒**：页面
 * `AT24C02_ADDRESS_READ 0xA0` 实为写地址、`AT24C02_ADDRESS_WRITE 0xA1`
 * 实为读地址——本实现按 0xA0=写/0xA1=读纠正命名）；字节写 = 地址+写 →
 * 字节地址 → 数据 → 停止（停止后进入内部擦写周期 ~5ms，期间不响应）；
 * 随机读 = 伪写（地址+写 → 字节地址）→ 重 start + 地址+读 → 读 1 字节
 * （主机 NACK）→ 停止；页写 = 字节写同启动，最多 16 字节（页边界内）；
 * 连续读 = 随机读启动后逐字节 ACK 直到主机 NACK + 停止（地址计数器自动
 * 递增、256 边界翻转）。
 * ⚠️ 页面缺陷修正清单（全部 notes 记录 + 测试守卫防回潮）：
 *  ① 地址宏名颠倒（主缺陷）：页面「SLAVE ADDRESS+W为0xA0…+R为0xA1」+
 *     READ 宏挂 0xA0/WRITE 宏挂 0xA1（宏名与语义互换，功能因调用巧合正确）
 *     → 命名纠正 AT24C02_ADDR_WRITE/READ，值保留页面原式；
 *  ② 读写路径应答全丢弃（WriteByte/ReadByte 三次 WaitAck 结果不检查——
 *     WriteByte void 页面原式保留（mspm0 同款）；read_byte 无应答返回 0xFF
 *     页面同款（与合法 0xFF 不可分——调用方先写后读验证）；write_page/
 *     read_block 补 2=无应答返回；
 *  ③ 注释 48/66 不符（main 演示——不落库）；④ main %d 打 unsigned char
 *     （演示——不落库）；
 *  ⑤ 写周期 5ms 未封装（main 裸 delay_ms(5)）→ at24c02_wait_write_done；
 *  ⑥ 页写/连续读正文有述、代码未实现 → 按正文补齐（跨页边界/len>16 拒收
 *     ——页面「超过 P+1 字节地址计数器自动翻转、先前数据被覆盖」防患）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/control--at24c02-eeprom-memory.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main.c 演示与 printf、
 * 函数名规范化（AT24C02_WriteByte/ReadByte → at24c02_write_byte/read_byte）、
 * I2C 原语静态化、引脚宏参数化、写周期延时走 delay 模块（页面演示
 * `delay_ms(5)` → at24c02_wait_write_done 封装）。模块板 WP 写保护脚由硬件
 * 接线管理（VCC 读保护/GND 可写），驱动不控制。 */

#define AT24C02_ADDR       (0x50u) /* 7 位器件地址（A2A1A0 = 000；8 枚级联按 A0-A2） */
#define AT24C02_ADDR_WRITE (AT24C02_ADDR << 1)         /* 0xA0（页面原式值） */
#define AT24C02_ADDR_READ  ((AT24C02_ADDR << 1) | 1u) /* 0xA1（页面原式值） */

#define AT24C02_SIZE     256u /* 存储容量 2K 位 = 256 字节 */
#define AT24C02_PAGE_SIZE 16u /* 页写缓冲（页面 P=15 附加字节） */
#define AT24C02_WRITE_CYCLE_MS 5u /* 内部擦写周期（页面演示 delay_ms(5)） */

/* at24c02_init：I2C 存储器无初始化序列（即插即用，页面演示无 init），空实现
 * 占位保持模块 API 一致；引脚配置由 init 内 gpio_init 完成（页面原式 OD +
 * 两脚置高）；在线校验由读写判（无应答 = 未接/写周期中）。 */
void at24c02_init(void);

/* at24c02_write_byte：字节写（页面原式：地址+写 0xA0 → 字节地址 → 数据 →
 * 停止）；返回后进入内部写周期（AT24C02_WRITE_CYCLE_MS ≈5ms），期间
 * 器件不响应——下次访问前调用 at24c02_wait_write_done()。 */
void at24c02_write_byte(uint8_t addr, uint8_t data);

/* at24c02_read_byte：随机读单字节（页面原式：伪写定位 → 重 start + 地址+读
 * 0xA1 → NACK → 停止），返回读到的数据；无应答时返回 0xFF（页面同款——
 * 区分不了合法 0xFF，调用方按业务判定/先写后读验证）。 */
uint8_t at24c02_read_byte(uint8_t addr);

/* at24c02_wait_write_done：等待内部写周期完成（delay_ms(AT24C02_WRITE_CYCLE_MS)
 * ——页面演示写后 delay_ms(5) 再读；页写同样适用）。 */
void at24c02_wait_write_done(void);

/* at24c02_write_page：页写（页面正文页写协议：16 字节内一次性写入，停止后
 * 单写周期烧写）；返回 0 = 成功、1 = 参数错误（len=0 / len>16 / 跨页边界——
 * 页面「超过 P+1 字节地址计数器自动翻转覆盖」防患）、2 = 通信无应答。
 * 成功返回后进入写周期，下次访问前调用 at24c02_wait_write_done()。 */
uint8_t at24c02_write_page(uint8_t addr, const uint8_t *data, uint8_t len);

/* at24c02_read_block：连续读 len 字节（页面正文连续读协议：随机读启动 →
 * 逐字节 ACK（首字节也 ACK）/ 最后一字节 NACK → 停止；地址自动递增、256
 * 边界翻转——len 上限 255（uint8_t），跨 256 边界读完整圈需两次调用）；
 * 返回 0 = 成功、1 = 参数错误（buf NULL/len=0，判空用 0——F1 头无 NULL）、
 * 2 = 通信无应答。 */
uint8_t at24c02_read_block(uint8_t addr, uint8_t *buf, uint8_t len);

#endif /* AT24C02_STM32_H */
