/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《人体红外传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/human-body-infrared-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "human_ir_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* HC-SR501 人体红外感应（stm32 纯驱动）：三线制 VCC/GND/OUT——模块被感应
 * 到人体时 OUT 输出高电平（模块介绍「人进入其感应范围则输出高电平」/
 * 规格「电平输出：高3.3V/低0V」；⚠️ 页面函数注释「0=感应到人体红外」与
 * 正文/规格矛盾——按 HC-SR501 器件标准「高=感应到」修正，notes 记录；
 * 页面代码 L108 实际也按高=1 实现（GPIO_ReadInputDataBit ? Bit_SET :
 * Bit_RESET））。
 * 极性单点反相宏 HUMAN_IR_TRIGGER_LEVEL（照 ttp224 TTP224_TOUCH_LEVEL
 * 先例）。轮询不注册 GPIO 中断（HC-SR501 输出脉冲慢速、无中断需求；
 * mspm0 线「共享实例 ISR 唯一」先例）。 */

void human_ir_init(void)
{
    gpio_init(HUMAN_IR_GPIO, HUMAN_IR_PIN, IU); /* 内部上拉输入（页面 IPU） */
}

uint8_t human_ir_read(void)
{
    uint8_t level = gpio_get(HUMAN_IR_GPIO, HUMAN_IR_PIN);
    return (level == HUMAN_IR_TRIGGER_LEVEL) ? 1 : 0; /* 1=感应到人体 */
}
