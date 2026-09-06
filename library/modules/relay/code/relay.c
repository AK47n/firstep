/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《继电器模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/control/relay-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "relay.h"
#include "ti_msp_dl_config.h" /* RELAY_PORT / RELAY_OUT_PIN
                                * （SysConfig 生成命名：<实例>_<引脚名>_PIN
                                * + 单 <实例>_PORT 宏；单脚输出实例，
                                * IR_TX/GP2Y1014 先例） */

/* 1 路 5V 继电器模块（mspm0 纯驱动）：页面 Set_Relay_Switch（0=吸合/1=断开）
 * 归一化为 relay_set（1=吸合/0=断开）+ 单点极性宏 RELAY_ON_LEVEL（默认 0u
 * = 引脚低电平吸合——页面「低电平吸合」模块）。 */

/* 页面 RELAY_OUT 宏原式保留为底层：x ? 引脚高 : 引脚低（页面
 * DL_GPIO_setPins/clearPins 分发，GPIO_IN1_PIN → RELAY_OUT_PIN） */
#define RELAY_OUT(x) \
    ((x) ? DL_GPIO_setPins(RELAY_PORT, RELAY_OUT_PIN) \
         : DL_GPIO_clearPins(RELAY_PORT, RELAY_OUT_PIN))

void relay_init(void)
{
    /* 初始断开（页面演示「上电即吸合」——演示语义归生成骨架） */
    relay_set(0);
}

void relay_set(uint8_t state)
{
    /* 归一化：1=吸合/0=断开；吸合电平 = RELAY_ON_LEVEL（默认 0u = 引脚低
     * 电平吸合）——state=1 → 引脚 RELAY_ON_LEVEL（0u → clearPins）、
     * state=0 → 引脚 1-RELAY_ON_LEVEL（1u → setPins） */
    RELAY_OUT((uint8_t)(state ? RELAY_ON_LEVEL : (uint8_t)(1u - RELAY_ON_LEVEL)));
}
