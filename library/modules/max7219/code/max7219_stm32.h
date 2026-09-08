/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《8位数码管显示模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/screen/8-bit-led-tube.html
 * 与《4合1 MAX7219 点阵显示模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/screen/max7219-matrix-display.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef MAX7219_STM32_H
#define MAX7219_STM32_H

#include <stdint.h>

/* MAX7219 数码管/点阵驱动（stm32，纯驱动切片，ADR 0009）：软 SPI 位操作
 * 3 脚（DIN/CLK/CS，不必占硬件 SPI 外设——不占 TIMER），同一芯片双显示
 * 形态——数码管 8 位（BCD 译码）与 4合1 点阵（无译码，行直通）；API 与
 * mspm0 版完全对齐（max7219_init/write_digit/write_matrix/write_reg/
 * clear/set_chip_count，同函数名/同语义/同参数——stm32 版总线层换
 * gpio_set 位操作）。
 * 引脚 = pin_config.h 单源 6 宏：MAX7219_DIN_GPIO/_DIN_PIN 默认 PC13、
 * _CLK_GPIO/_CLK_PIN 默认 PC14、_CS_GPIO/_CS_PIN 默认 PC15——**叠板载
 * LED 三灯（PC13-15）**：显示件与板载指示灯为**输出指示互替**（有数码管/
 * 点阵就不用板载灯——互替同脚先例：ttp224×key_matrix），同选经引脚绑定
 * 消解；三脚同口（默认组内无跨口换脚约束——逐脚宏族，换单脚经绑定行级
 * 覆写）；与 lcd/oled 显示族互替同脚（一次选一块屏——大屏/小屏/数码管）
 * 不同框、同选概率最低；页面默认脚（mspm0 板脚 PB9/PA18/PB18）不照抄。
 * 协议（MAX7219 数据手册）：16 位包 = 寄存器地址字节 + 数据字节，MSB 先；
 * CS 低选通、第 16 个 CLK 上升沿后 CS 上升沿锁存；寄存器 0x01-0x08 = 位/
 * 行 1-8，0x09 译码方式（0xFF = 全位 BCD、0x00 = 无译码），0x0A 亮度
 * （0-15），0x0B 扫描界限（0x07 = 8 位/行全开——上游数码管页注释「4 个数码管
 * 显示」与代码 0x07 矛盾，0x03 才是 4 位），0x0C 掉电（0x01 = 普通模式），
 * 0x0F 显示测试（0x00 = 正常——上游数码管页 init 写 0x01 全亮再靠 main 关，
 * 本实现 init 直接归正常）。
 * 级联：16 位包沿 DOUT→DIN 链移位，第一个包落在最远片——先发最远片数据
 * （4合1 点阵页 demo 的「第一/二/三/四点阵」命名按发送序而非物理链序，且其
 * Max7219_Lock 为 CS(1) 后立刻 CS(0) 的脉冲锁存，本实现按标准锁存（CS(0) 发
 * 包 → CS(1) 锁存）修正，行为等价更规范）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/screen--8-bit-led-tube.md
 * 与 screen--max7219-matrix-display.md（立创 wiki 地阔星移植手册；两页同芯片
 * 同驱动内核——合并为单模块双形态，代码按模块库规范改写：去 main.c 演示与
 * printf、函数名规范化、引脚宏参数化、演示字模表不随库入库）。 */

#define MAX7219_FORM_DIGIT  0u  /* 8 位数码管（BCD 译码） */
#define MAX7219_FORM_MATRIX 1u  /* 4合1 点阵（行直通无译码） */

/* max7219_init：按形态初始化（译码方式/扫描界限/亮度/普通模式/结束显示测试）
 * 并清屏；brightness 0-15（超出钳位），form = MAX7219_FORM_DIGIT/MATRIX；
 * stm32 版内含三脚 GPIO 初始化（gpio_init OUT_PP——页面原式推挽）。 */
void max7219_init(uint8_t form, uint8_t brightness);

/* max7219_write_digit：数码管单（位 1-8）写 BCD 值——0-9 数字、0x0A '-'、
 * 0x0B 'E'、0x0C 'H'、0x0D 'L'、0x0E 'P'、0x0F 熄灭；写第一片（级联多片时
 * 其他片用 max7219_write_reg 寻址）。 */
void max7219_write_digit(uint8_t digit, uint8_t value);

/* max7219_write_matrix：点阵写 8 行字模 × 级联片数（1-4 片）；
 * rows = 每片 8 字节（片 0 在前，行 0 = 寄存器 0x01 自上而下，
 * 字节内位 7（MSB）= 最左列、1 = 点亮），行逐行锁存。 */
void max7219_write_matrix(const uint8_t *rows, uint8_t matrices);

/* max7219_write_reg：底层寄存器写（chip 0..片数-1，addr/data 见协议注释）。 */
void max7219_write_reg(uint8_t chip, uint8_t addr, uint8_t data);

/* max7219_clear：全灭（数码管形态 = BCD 0x0F、点阵形态 = 行 0x00）。 */
void max7219_clear(void);

/* max7219_set_chip_count：级联片数（1-4，默认 1；write_matrix 会按其参数
 * 同步该值）。 */
void max7219_set_chip_count(uint8_t count);

#endif /* MAX7219_STM32_H */
