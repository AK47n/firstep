#include "huidu.h"

uint8_t huidu_value[] = {0, 0, 0, 0, 0, 0, 0, 0};

static uint8_t get_gpio_state(GPIO_Regs *gpio_port, uint32_t gpio) {
    uint32_t high_bits = DL_GPIO_readPins(gpio_port, gpio);
    // 传感器：黑线→低电平(0)，白区域→高电平(1)
    // 但整个项目约定 huidu_value[i]==1 表示检测到黑线，所以这里翻转
    if((high_bits & gpio) != 0) return 0;  // 高电平 = 白
    else return 1;                          // 低电平 = 黑
}

void huidu_get_value()
{
    huidu_value[0] = get_gpio_state(HUIDU_L3_PORT, HUIDU_L3_PIN);
    huidu_value[1] = get_gpio_state(HUIDU_L2_PORT, HUIDU_L2_PIN);
    huidu_value[2] = get_gpio_state(HUIDU_L1_PORT, HUIDU_L1_PIN);
    huidu_value[3] = get_gpio_state(HUIDU_R1_PORT, HUIDU_R1_PIN);
    huidu_value[4] = get_gpio_state(HUIDU_R2_PORT, HUIDU_R2_PIN);
    huidu_value[5] = get_gpio_state(HUIDU_L4_PORT, HUIDU_L4_PIN);
    huidu_value[6] = get_gpio_state(HUIDU_R3_PORT, HUIDU_R3_PIN);
    huidu_value[7] = get_gpio_state(HUIDU_R4_PORT, HUIDU_R4_PIN);
}
