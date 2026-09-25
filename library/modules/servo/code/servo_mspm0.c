#include "servo.h"
#include "ti_msp_dl_config.h"

/* 舵机（mspm0，PWM 底座）：周期与脉宽按 SERVO_PWM_INST_CLK_FREQ 运行时
 * 计算（照 step_motor 先例，不依赖母版 ULPCLK 假设）：
 *   周期 = 1s / SERVO_FREQ_HZ 的计数值
 *   脉宽 = 角度换算（servo.h 的 SERVO_PULSE_US 单源）→ 按周期比例折算
 *
 * ── 量程：SERVO_PWM 是 TIMG8 = **16 位计数器**（driver-defect-fixes/02）────
 * SDK 的 SysConfig 元数据把这条写死（`PWMTimerMSPM0.syscfg.js`）：**TIMG =
 * 16-bit counter + 8-bit prescaler**，只有 TIMG12 是 32-bit 且不带预分频；
 * 元数据还会在 `timerCount > 65535` 时报 "Timer Count Exceeds non-TIMG12
 * bounds"，母版这处写成上限 65535 就是这条。
 * 而 `DL_Timer_setLoadValue` 只做 `COUNTERREGS.LOAD = value`（SDK
 * `dl_timer.h`，**不钳位**），LOAD 在这颗 16 位实例上只有低 16 位有效
 * ⇒ 旧实现直接写 `SERVO_PWM_INST_CLK_FREQ / 50` = 640000 会被截成
 * 50176：周期 ≈1.57ms（≈638Hz）而不是 20ms，且比较值在 ≈96° 以上超过周期
 * ⇒ **输出恒高**（学生看到的是「舵机不动 / 只在某个角度区间能动」）。
 * 修法取工单 02 的二选一之②——**用母版侧配好的分频**：母版把
 * `SERVO_PWM.clockPrescale` 配成 16 ⇒ 计数时钟 2MHz ⇒ 20ms = 40000 计数
 * < 65535，运行时只写周期与比较值。**刻意不「加个钳位」**：钳位会把 50Hz
 * 变成别的频率（不崩，但也不对）。 */

#define SERVO_TIMER_MAX_COUNT 65535u /* TIMGx 16 位计数器上限（SysConfig 元数据同款） */

/* 编译期守住量程：母版的分频被改小、或这颗实例被换成 32MHz 直供时**当场红**，
 * 而不是悄悄输出一个错的频率。
 * 下面那条 `#error` 的文案**故意只写 ASCII**：它是编译器诊断，会原样进构建日志，
 * 而多字节代码页的编译器对非 ASCII 诊断串历来不稳（本仓 Keil 那侧有实测教训）；
 * 中文说明一律留在注释里——注释永远是安全的。 */
#if (SERVO_PWM_INST_CLK_FREQ / SERVO_FREQ_HZ) > SERVO_TIMER_MAX_COUNT
#error "SERVO_PWM clock too fast: the 20ms period does not fit a 16-bit counter. Raise SERVO_PWM.clockPrescale in the mspm0 master syscfg."
#endif

static uint32_t servo_period(void)
{
    return SERVO_PWM_INST_CLK_FREQ / SERVO_FREQ_HZ;
}

static uint32_t servo_duty_for_angle(uint16_t angle)
{
    uint32_t period = servo_period();
    /* 64 位中间量：period 最大 ~1.6e6（80MHz/50）× 脉宽 2500us 会溢出 32 位 */
    return (uint32_t)((uint64_t)period * SERVO_PULSE_US(angle) / SERVO_PERIOD_US);
}

void servo_init(uint8_t servo_id, uint8_t channel)
{
    (void)servo_id;
    (void)channel;
    /* EDGE_ALIGN 的语义是 `LOAD = period - 1`（SDK dl_timer.h 的 PWMConfig
     * 说明原文），所以写 servo_period() - 1 才是整整 20ms——stm32 侧
     * `ARR = 1000000 / fre - 1` 同款，两侧对偶。 */
    DL_Timer_setLoadValue(SERVO_PWM_INST, servo_period() - 1u);
    DL_Timer_setCaptureCompareValue(
        SERVO_PWM_INST, servo_duty_for_angle(0), GPIO_SERVO_PWM_C0_IDX);
    DL_Timer_startCounter(SERVO_PWM_INST);
}

void servo_set_angle(uint8_t servo_id, uint16_t angle)
{
    (void)servo_id;
    if (angle > SERVO_ANGLE_MAX) {
        angle = SERVO_ANGLE_MAX;
    }
    DL_Timer_setCaptureCompareValue(
        SERVO_PWM_INST, servo_duty_for_angle(angle), GPIO_SERVO_PWM_C0_IDX);
}
