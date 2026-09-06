/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《微波多普勒无线雷达传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/microwave-doppler-radar-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "microwave_radar_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* HB100 微波多普勒雷达（stm32 纯驱动）：三线制 VCC/GND/OUT——模块检测到
 * 物体移动时 OUT 输出低电平（页面函数注释「1=未检测到物体移动 0=检测到
 * 物体移动」+ main 演示（OUT 输入为 0 判移动）同口径，页面自一致；正文
 * 未声明极性——HB100 带底板 OUTPUT 极性因底板而异，未上板）；极性单点
 * 反相宏 MICROWAVE_TRIGGER_LEVEL（照 ttp224 TTP224_TOUCH_LEVEL 先例；
 * 实物输出反相改 1 即可）。页面宏名无前缀（RCC_OUT/PORT_OUT/GPIO_OUT/
 * OUT_IN）有撞名风险 → 本件统一 MICROWAVE_ 前缀（notes 记录）。轮询不
 * 注册中断（微波脉冲慢速；mspm0 线「共享实例 ISR 唯一」先例）；页面
 * main 演示的开/关门时序逻辑归生成骨架（ADR 0009）。 */

void microwave_radar_init(void)
{
    gpio_init(MICROWAVE_GPIO, MICROWAVE_PIN, IU); /* 内部上拉输入（页面 IPU） */
}

uint8_t microwave_radar_read(void)
{
    uint8_t level = gpio_get(MICROWAVE_GPIO, MICROWAVE_PIN);
    return (level == MICROWAVE_TRIGGER_LEVEL) ? 1 : 0; /* 1=检测到移动 */
}
