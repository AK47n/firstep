#include "sr04.h"
#include "delay.h" /* delay_us / delay_ms：触发与时序等待 */
#include "ti_msp_dl_config.h" /* SR04_PORT / SR04_TRIG_PIN / SR04_ECHO_PIN / CPUCLK_FREQ */

/* 忙等测宽：ECHO 高电平期间自旋计数，测得循环次数 → 换算 us。
 * 校准常数 = 忙等循环的单次迭代周期数。32MHz 下一条 volatile 读 + 比较 +
 * 增量 ≈ 6-8 周期 ≈ 0.2us/迭代；用 SR04_LOOP_NS 单源换算（= 迭代估计周期
 * 数 × 1000 / CPUCLK_FREQ）。分辨率 ~0.25us 足够（1cm = 58us）。 */
#define SR04_LOOP_US 0.25f /* 单次迭代近似耗时（us），保守向上取整 */

void sr04_init(void)
{
    DL_GPIO_clearPins(SR04_PORT, SR04_TRIG_PIN);
}

/* sr04_echo_pulse_us：触发并测一次回声脉宽；返回脉宽 us（0 = 超时/无回波）。
 * 忙等实现：无定时器依赖（地猛星 SysConfig TIMER 实例仅暴露 TIMG0/6/7/8/12，
 * 已被 motor/pid/ntb_time/servo/step_motor 全占——测宽不占外设）。 */
static uint32_t sr04_echo_pulse_us(void)
{
    volatile uint32_t count = 0;
    uint32_t timeout;

    /* 触发：TRIG 高 ≥10us */
    DL_GPIO_clearPins(SR04_PORT, SR04_TRIG_PIN);
    delay_us(10);
    DL_GPIO_setPins(SR04_PORT, SR04_TRIG_PIN);
    delay_us(15);
    DL_GPIO_clearPins(SR04_PORT, SR04_TRIG_PIN);

    /* 等 ECHO 拉高（超时 30ms = 无回波/超量程） */
    timeout = 0;
    while (!(DL_GPIO_readPins(SR04_PORT, SR04_ECHO_PIN) & SR04_ECHO_PIN)) {
        delay_cycles(CPUCLK_FREQ / 1000 / 100); /* 10us/次 */
        if (++timeout > SR04_TIMEOUT_US / 10u) {
            return 0;
        }
    }
    /* 忙等计数 ECHO 高电平宽度 */
    while (DL_GPIO_readPins(SR04_PORT, SR04_ECHO_PIN) & SR04_ECHO_PIN) {
        count++;
        if (count > (uint32_t)(SR04_TIMEOUT_US + 36000u) / SR04_LOOP_US) {
            /* 66ms 手册最坏上限（30ms 量程 + 36ms 余量），防拆机死等 */
            break;
        }
    }
    if (count == 0) {
        return 0;
    }
    return (uint32_t)(count * SR04_LOOP_US);
}

float sr04_get_distance_cm(void)
{
    float sum = 0.0f;
    uint8_t i;
    for (i = 0; i < SR04_SAMPLE_COUNT; i++) {
        uint32_t us = sr04_echo_pulse_us();
        if (us == 0) {
            return 0.0f; /* 任一次超时 → 整次返回 0（防平均拉虚） */
        }
        sum += (float)us / 58.0f; /* us → cm（声速 340m/s 往返） */
        delay_ms(100);            /* 立创原版：测量间隔，防回声混叠 */
    }
    return sum / (float)SR04_SAMPLE_COUNT;
}
