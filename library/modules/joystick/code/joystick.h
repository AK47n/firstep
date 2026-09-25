/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《双轴按键摇杆模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/control/two-axis-keystroke-rocker-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef JOYSTICK_H
#define JOYSTICK_H

#include <stdint.h>

/* 双轴摇杆按键驱动（mspm0 纯驱动，ADR 0009）：
 * - X/Y 两轴：ADC12_0 实例共享（b1-adc-servo/01 的 adc 模块同实例，sequence
 *   **八槽**模式 startAdd=0 / endAdd=7，槽位 8/8 用满——MEM3 归 ir_distance、
 *   MEM4-7 归 mq135/mq5/flame/soil，wiki-modules-batch2/04 与 batch7/8）：
 *   JOYSTICK_X = MEM1（default PA26/A0_1）、JOYSTICK_Y = MEM2（default PA25/A0_2），
 *   轮询读取 + 4 次快速平均，12bit 原始值（0-4095），
 *   percent 版按 4095 归一 0-100%；
 * - SW 按键：JOYSTICK_SW 上拉输入（default PA9），按下接地低电平。
 * 引脚/极性由母版 syscfg 与宏决定（JOYSTICK_PORT / JOYSTICK_SW_PIN /
 * ADC12_0_INST / ADC12_0_ADCMEM_1 / ADC12_0_ADCMEM_2），模块代码零引脚字面量。
 * 默认脚与既有模块刻意重叠（PA26/PA25 = ZIGBEE_UART、PA9 = DIGIT_UART RX），
 * 同选时经引脚绑定消解（见 manifest notes）。 */

#define JOYSTICK_SW_PRESSED_LEVEL 0 /* 1=按下（低有效） */

/* 本次采样无效（driver-defect-fixes/01）：read_x / read_y 与两个 percent 版
 * 在**一圈都没采到**时返回它——含义是「这次没读到」，**不是读数**。
 * 为什么非要有这个值：0 是合法读数（raw 0 = 杆推到端点，percent 0 = 0%），
 * 拿 0 当失败标记就分不开「坏了」与「推到端点」；而 raw 满量程 4095、
 * percent 满量程 100，65535 两者都到不了。
 * ⚠ 只有 mspm0 侧有这个概念：stm32 侧读母版 ml_adc 的 adc_get（无显式超时），
 * 不存在「等到超时」这条路径，故那侧的行为一字未动。 */
#define JOYSTICK_ADC_INVALID 0xFFFFu

void joystick_init(void);
uint16_t joystick_read_x(void);          /* X 轴 12bit 原始值（0-4095；65535=本次无效） */
uint16_t joystick_read_y(void);          /* Y 轴 12bit 原始值（0-4095；65535=本次无效） */
uint16_t joystick_read_x_percent(void);  /* X 轴 0-100%（65535=本次无效） */
uint16_t joystick_read_y_percent(void);  /* Y 轴 0-100%（65535=本次无效） */
uint8_t joystick_read_sw(void);          /* 1=按下，0=松开 */

#endif /* JOYSTICK_H */
