/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《继电器模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/relay-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "relay_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* 1 路 5V 继电器模块（stm32 纯驱动切片，ADR 0009）：页面
 * Set_Relay_Switch（0=吸合/1=断开）归一化为 relay_set（1=吸合/0=断开）
 * + 单点极性宏 RELAY_ON_LEVEL（默认 0u = 引脚低电平吸合——页面「低电平
 * 吸合」模块：IN1 输出低电平 → 光耦 1/2 脚导通 → 三极管基极得电 → 三极管
 * 导通 → 线圈得电 → 触点由常闭吸合到常开）。
 *
 * ⚠️ 页面甄别记录（F4 嫌疑页）：整页为 **F4 口径**（stm32f4xx.h +
 * RCC_AHB1PeriphClockCmd + GPIO_Mode_OUT/GPIO_OType_PP/GPIO_PuPd_UP/
 * GPIO_Speed_100MHz），与页面标题（F103）自相矛盾——疑似从 F4 板页面
 * 复制未迁移。按 F1 换算表逐行翻译：RCC_AHB1PeriphClockCmd×(APB1) →
 * RCC_APB2PeriphClockCmd(APB2)；GPIO_Mode_OUT+OType_PP+PuPd_UP+
 * Speed_100MHz → GPIO_Mode_Out_PP+Speed_50MHz（F1 无 OType/PuPd 字段，
 * 结构体删两行；F1 最高 50MHz）；GPIO_WriteBit 同名（F1 标准库确认存在）。
 * 本实现直接走母版 ml_gpio（gpio_init 内部使能 APB2 时钟 + 推挽输出
 * 50MHz + 初始电平），等价页面流程，零寄存器级/标准库调用。 */

/* 页面 RELAY_OUT(x) = GPIO_WriteBit(PORT, GPIO, x?Bit_SET:Bit_RESET)
 * 原式保留为底层：x ? 引脚高 : 引脚低（GPIO_SetBits/ResetBits/WriteBit →
 * gpio_set 统一） */
#define RELAY_OUT(x) gpio_set(RELAY_GPIO, RELAY_PIN, (x))

void relay_init(void)
{
    gpio_init(RELAY_GPIO, RELAY_PIN, OUT_PP);
    /* 初始断开（页面演示「上电即吸合」——演示语义归生成骨架） */
    relay_set(0);
}

void relay_set(uint8_t state)
{
    /* 归一化：1=吸合/0=断开；吸合电平 = RELAY_ON_LEVEL（默认 0u = 引脚低
     * 电平吸合）——state=1 → 引脚 RELAY_ON_LEVEL（0u → 低=吸合）、
     * state=0 → 引脚 1-RELAY_ON_LEVEL（1u → 高=断开） */
    RELAY_OUT((uint8_t)(state ? RELAY_ON_LEVEL : (uint8_t)(1u - RELAY_ON_LEVEL)));
}
