#include "motor.h"

/* ============================================================
 * TB6612 双路直流电机驱动（MSPM0 纯驱动切片，ADR 0009）
 *   - PWM 调速：motor_set_duty
 *   - 方向控制：motor_set_direction（0 停 / 1 正转 / 2 反转）
 *   - 编码器计数：GROUP1_IRQHandler 累加 counter_1_A/counter_2_A，
 *     motor_encoder_read 读后清零（xunji / pid 等经此 API 取数）
 * ============================================================ */

uint32_t counter_1_A = 0;  // 电机1编码器 A 相脉冲计数（GPIO 中断累加）
uint32_t counter_2_A = 0;  // 电机2编码器 A 相脉冲计数（GPIO 中断累加）

void motor_init(uint8_t motor_id)
{
    /* STBY 已改为硬件直接接 3.3V，不再由 MCU 控制 */
    if (motor_id == 1) {
        DL_GPIO_setPins(DC_MOTOR_AIN1_PORT, DC_MOTOR_AIN1_PIN);
        DL_GPIO_setPins(DC_MOTOR_AIN2_PORT, DC_MOTOR_AIN2_PIN);
        DL_Timer_setCaptureCompareValue(PWMAB_INST, 0, GPIO_PWMAB_C0_IDX);
    } else if (motor_id == 2) {
        DL_GPIO_setPins(DC_MOTOR_BIN1_PORT, DC_MOTOR_BIN1_PIN);
        DL_GPIO_setPins(DC_MOTOR_BIN2_PORT, DC_MOTOR_BIN2_PIN);
        DL_Timer_setCaptureCompareValue(PWMAB_INST, 0, GPIO_PWMAB_C1_IDX);
    }
    DL_Timer_startCounter(PWMAB_INST);
}

// 限幅函数：PWM 占空比上限 1300（0~1300，对偶 pid 模块 MAX_DUTY）
int limit_duty(int duty)
{
    if (duty > 1300) {
        duty = 1300;
    }
    if (duty < 0) {
        duty = 0;
    }
    return duty;
}

void motor_set_duty(uint8_t motor_id, uint32_t duty)
{
    duty = limit_duty(duty);
    if (motor_id == 1) {
        DL_Timer_setCaptureCompareValue(PWMAB_INST, duty, GPIO_PWMAB_C0_IDX);
    } else if (motor_id == 2) {
        DL_Timer_setCaptureCompareValue(PWMAB_INST, duty, GPIO_PWMAB_C1_IDX);
    }
}

// direction: 0 停止，1 正转，2 反转
void motor_set_direction(uint8_t motor_id, uint8_t direction)
{
    if (motor_id == 1) {
        if (direction == 0) {
            DL_GPIO_setPins(DC_MOTOR_AIN1_PORT, DC_MOTOR_AIN1_PIN);
            DL_GPIO_setPins(DC_MOTOR_AIN2_PORT, DC_MOTOR_AIN2_PIN);
        } else if (direction == 1) {
            DL_GPIO_setPins(DC_MOTOR_AIN1_PORT, DC_MOTOR_AIN1_PIN);
            DL_GPIO_clearPins(DC_MOTOR_AIN2_PORT, DC_MOTOR_AIN2_PIN);
        } else if (direction == 2) {
            DL_GPIO_clearPins(DC_MOTOR_AIN1_PORT, DC_MOTOR_AIN1_PIN);
            DL_GPIO_setPins(DC_MOTOR_AIN2_PORT, DC_MOTOR_AIN2_PIN);
        }
    } else if (motor_id == 2) {
        if (direction == 0) {
            DL_GPIO_setPins(DC_MOTOR_BIN1_PORT, DC_MOTOR_BIN1_PIN);
            DL_GPIO_setPins(DC_MOTOR_BIN2_PORT, DC_MOTOR_BIN2_PIN);
        } else if (direction == 1) {
            DL_GPIO_setPins(DC_MOTOR_BIN1_PORT, DC_MOTOR_BIN1_PIN);
            DL_GPIO_clearPins(DC_MOTOR_BIN2_PORT, DC_MOTOR_BIN2_PIN);
        } else if (direction == 2) {
            DL_GPIO_clearPins(DC_MOTOR_BIN1_PORT, DC_MOTOR_BIN1_PIN);
            DL_GPIO_setPins(DC_MOTOR_BIN2_PORT, DC_MOTOR_BIN2_PIN);
        }
    }
}

/* 读左右轮编码器脉冲计数并清零（速度计算由调用方按采样周期换算） */
void motor_encoder_read(int32_t *left, int32_t *right)
{
    *left = (int32_t)counter_1_A;
    counter_1_A = 0;
    *right = (int32_t)counter_2_A;
    counter_2_A = 0;
}

/* 编码器 GPIO 中断：A 相脉冲累加（B 相方向由调用方结合电机方向判断）。
 * 引脚组走 syscfg 生成的 DC_MOTOR_AA/BA_PORT 宏（AA=PA16、BA=PB19，
 * 改接线只改母版 mspm0.syscfg 的 $assign）。 */
void GROUP1_IRQHandler(void)
{
    switch (DL_GPIO_getPendingInterrupt(DC_MOTOR_BA_PORT))
    {
    case DC_MOTOR_BA_IIDX:
        counter_2_A++;
        break;

    default:
        break;
    }

    switch (DL_GPIO_getPendingInterrupt(DC_MOTOR_AA_PORT))
    {
    case DC_MOTOR_AA_IIDX:
        counter_1_A++;
        break;

    default:
        break;
    }
}
