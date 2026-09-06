/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《AT24C02-EEPROM存储器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/control/at24c02-eeprom-memory.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef AT24C02_H
#define AT24C02_H

#include <stdint.h>

/* AT24C02 EEPROM 存储器驱动（mspm0，纯驱动切片，ADR 0009）：软 I2C 位操作
 * （SCL/SDA 两 GPIO，不必占硬件 I2C 外设，照 aht10 先例——IIC 原语静态化、
 * SDA 方向运行时切换、延时走 delay 模块），字节写/读（页面原式）+ 页写
 * （16 字节页缓冲，跨页边界拒收——页面正文「超过 P+1 字节地址计数器自动
 * 翻转、先前数据被覆盖」防患）+ 连续读（页面正文「连续读」描述实现）+
 * 写周期等待（~5ms 走 delay 模块）。
 * 引脚 = 母版 syscfg 实例 AT24C02：SCL（输出，默认 PB24——与 STEP_MOTOR
 * RST2 / SR04 TRIG / HC05 KEY 默认重叠，同选时经引脚绑定消解）/ SDA（双向，
 * 默认 PB8——与 STEP_MOTOR DCY2 / SR04 ECHO 同脚）。SDA 方向运行时切换
 * （写 = 输出，读 ACK/数据 = 输入），DL_GPIO_initDigitalOutput/Input 由本
 * 驱动调用。
 * 通信协议（AT24C02 数据手册 / 立创移植手册）：7 位器件地址 0x50（A2A1A0 =
 * 000，一条总线可挂 8 枚），8 位写/读 = 0xA0/0xA1（页面宏值；**页面宏名
 * 颠倒**：页面 `AT24C02_ADDRESS_READ 0xA0` 实为写地址、`AT24C02_ADDRESS_WRITE
 * 0xA1` 实为读地址——本实现按 0xA0=写/0xA1=读纠正命名）；字节写 = 地址+写
 * → 字节地址 → 数据 → 停止（停止后进入内部擦写周期 ~5ms，期间不响应）；
 * 随机读 = 伪写（地址+写 → 字节地址）→ 重 start + 地址+读 → 读 1 字节
 * （主机 NACK）→ 停止；页写 = 字节写同启动，最多 16 字节（页边界内）；
 * 连续读 = 随机读启动后逐字节 ACK 直到主机 NACK + 停止（地址计数器自动
 * 递增、256 边界翻转）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/control--at24c02-eeprom-memory.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去掉 main.c 演示与
 * printf、函数名规范化（AT24C02_WriteByte/ReadByte → at24c02_write_byte/
 * read_byte）、IIC 原语静态化、引脚宏参数化、写周期延时走 delay 模块
 * （页面演示 `delay_ms(5)` → at24c02_wait_write_done 封装）。页写/连续读
 * 为按页面正文实现（页面仅给字节读写代码）。模块板 WP 写保护脚由硬件
 * 接线管理（VCC 读保护/GND 可写），驱动不控制。 */

#define AT24C02_ADDR       (0x50u) /* 7 位器件地址（A2A1A0 = 000；8 枚级联按 A0-A2） */
#define AT24C02_ADDR_WRITE (AT24C02_ADDR << 1)         /* 0xA0（页面原式值） */
#define AT24C02_ADDR_READ  ((AT24C02_ADDR << 1) | 1u) /* 0xA1（页面原式值） */

#define AT24C02_SIZE     256u /* 存储容量 2K 位 = 256 字节 */
#define AT24C02_PAGE_SIZE 16u /* 页写缓冲（页面 P=15 附加字节） */
#define AT24C02_WRITE_CYCLE_MS 5u /* 内部擦写周期（页面演示 delay_ms(5)） */

/* at24c02_init：I2C 存储器无初始化序列（即插即用，页面演示无 init），空实现
 * 占位保持模块 API 一致；在线校验由读写判（无应答 = 未接/写周期中）。 */
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
 * 返回 0 = 成功、1 = 参数错误（buf NULL / len=0）、2 = 通信无应答。 */
uint8_t at24c02_read_block(uint8_t addr, uint8_t *buf, uint8_t len);

#endif /* AT24C02_H */
