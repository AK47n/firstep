/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《微波多普勒无线雷达传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/microwave-doppler-radar-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "microwave_radar.h"
#include "ti_msp_dl_config.h" /* MICROWAVE_PORT / MICROWAVE_OUT_PIN
                                * （SysConfig 生成命名：<实例>_<引脚名>_PIN
                                * + 单 <实例>_PORT 宏；单脚输入实例，
                                * TTP224 先例） */

/* HB100 微波多普勒雷达（mspm0 纯驱动）：三线制 VCC/GND/OUT——模块检测到
 * 物体移动时 OUT 输出低电平（页面函数注释「1=未检测到物体移动 0=检测到物体
 * 移动」+ main 演示（OUT 输入为 0 判移动）同口径，页面自一致）；
 * 极性单点反相宏 MICROWAVE_TRIGGER_LEVEL（照 ttp224 TTP224_TOUCH_LEVEL
 * 先例；实物输出反相改 1 即可）；页面 main 演示的开/关门时序逻辑归生成
 * 骨架（ADR 0009）。 */

static uint8_t microwave_radar_raw_level(void)
{
    uint32_t bits = DL_GPIO_readPins(MICROWAVE_PORT, MICROWAVE_OUT_PIN);
    return (bits & MICROWAVE_OUT_PIN) ? 1 : 0;
}

void microwave_radar_init(void)
{
    /* GPIO 输入（内部上拉）由 SYSCFG_DL_init() 配置，无需运行时初始化 */
}

uint8_t microwave_radar_read(void)
{
    uint8_t level = microwave_radar_raw_level();
    return (level == MICROWAVE_TRIGGER_LEVEL) ? 1 : 0; /* 1=检测到移动 */
}
