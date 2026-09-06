/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《TTP224触摸传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/ttp224-touch-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef TTP224_H
#define TTP224_H

#include <stdint.h>

/* TTP224 4 路电容触摸按键驱动（mspm0，纯驱动切片，ADR 0009）：4 × GPIO 输入
 * 上拉，read(channel) 返回单键 1=触摸/0=未触摸（channel 1-4，页面
 * Key_IN1-4 序），read_all() 返回低 4 位掩码（bit0=通道1 … bit3=通道4）。
 * 引脚 = 母版 syscfg 实例 TTP224：OUT1-4（输入 + 内部上拉，默认 PA22/PA25/
 * PA26/PA27——与 HUIDU 巡线/ZIGBEE/NRF/joystick/IR_REMOTE/ADC MEM3 重叠：
 * 触摸按键与无线链路/手动输入互替、与巡线/测距不同框，同选概率最低，同选
 * 时经引脚绑定消解；四脚与同批默认不撞）。
 * 极性（按页面资料）：模块被触摸时输出**高电平**（页面 TTP223B 正文描述与
 * 页面代码 KEY_INx 宏同口径）——read 直接按引脚电平返回 1=触摸；若实物为
 * 低有效（TTP224N 输出常为低有效），把 TTP224_TOUCH_LEVEL 改为 0 即可
 * 反相，其余零改动（单点反相宏）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/sensor--ttp224-touch-sensor.md
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf、页面 4 个
 * Key_INx_Scanf 收敛为 read(ch)/read_all、引脚宏参数化——四脚同 GPIOA，
 * 单 TTP224_PORT 宏 + 每脚 <实例>_<引脚名>_PIN，NRF24L01 先例）。 */

/* 触摸判定电平（单点反相宏）：1 = 引脚高 = 触摸（页面原样）；0 = 引脚低 =
 * 触摸（TTP224N 实物常见低有效，按需改此宏）。 */
#define TTP224_TOUCH_LEVEL 1u

#define TTP224_CHANNELS 4u /* 通道数（页面 OUT1-4） */

/* ttp224_init：GPIO 输入由 SYSCFG_DL_init() 配置（内部上拉），空实现占位
 * 保持 API 一致（joystick/sw 先例）。 */
void ttp224_init(void);

/* ttp224_read：读单键（channel 1-4，页面 Key_IN1-4 序；越界返回 0）。
 * 返回 1 = 触摸、0 = 未触摸（按 TTP224_TOUCH_LEVEL 极性）。 */
uint8_t ttp224_read(uint8_t channel);

/* ttp224_read_all：读全部 4 键，返回低 4 位掩码——bit0=通道1 … bit3=通道4，
 * 置位 = 触摸（支持多点同时触摸）。 */
uint8_t ttp224_read_all(void);

#endif /* TTP224_H */
