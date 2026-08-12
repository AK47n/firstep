#include "xunji.h"
#include "motor.h"

/* ---- 灰度 8 路（非零 = 白区，真机极性） ---- */
#define P1			DL_GPIO_readPins(HUIDU_L3_PORT,HUIDU_L3_PIN)
#define P2			DL_GPIO_readPins(HUIDU_L2_PORT,HUIDU_L2_PIN)
#define P3			DL_GPIO_readPins(HUIDU_L1_PORT,HUIDU_L1_PIN)
#define P4			DL_GPIO_readPins(HUIDU_R1_PORT,HUIDU_R1_PIN)
#define P5			DL_GPIO_readPins(HUIDU_R2_PORT,HUIDU_R2_PIN)
#define P6			DL_GPIO_readPins(HUIDU_L4_PORT,HUIDU_L4_PIN)
#define P7			DL_GPIO_readPins(HUIDU_R3_PORT,HUIDU_R3_PIN)
#define P8			DL_GPIO_readPins(HUIDU_R4_PORT,HUIDU_R4_PIN)

extern uint32_t counter_1_A, counter_2_A;   // key 模块 GPIO 中断累加（符号级 extern，需手动同选 key）

/* 电机输出：百分比制 → motor 原始占空比 0~1300（MAX_DUTY 对偶 pid 模块，
 * 13 = 1300/100）。方向：正→正转，负→反转（0停1正转2反转）。 */
#define XUNJI_MAX_DUTY  1300

void xunji_init(void)
{
    /* 无内部状态需要初始化：灰度 / 编码器 / 电机由母版外设布局与
     * 对应模块（huidu / key / motor）就绪，本模块只读服务。 */
}

uint8_t xunji_read_gray(void)
{
    uint8_t gray = 0;
    if (P1) gray |= 0x01;
    if (P2) gray |= 0x02;
    if (P3) gray |= 0x04;
    if (P4) gray |= 0x08;
    if (P5) gray |= 0x10;
    if (P6) gray |= 0x20;
    if (P7) gray |= 0x40;
    if (P8) gray |= 0x80;
    return gray;
}

// 加权质心巡线：对所有压线传感器做加权平均，输出连续差速值
// gain: 增益系数，值越大转向越激进
// 返回: 正=右转，负=左转，0=未检测到线
float xunji_centroid(float gain)
{
    uint8_t gray = xunji_read_gray();
    int32_t sum = 0;
    int32_t cnt = 0;

    if (gray & 0x01) { sum += -7; cnt++; }
    if (gray & 0x02) { sum += -5; cnt++; }
    if (gray & 0x04) { sum += -3; cnt++; }
    if (gray & 0x08) { sum += -1; cnt++; }
    if (gray & 0x10) { sum +=  1; cnt++; }
    if (gray & 0x20) { sum +=  3; cnt++; }
    if (gray & 0x40) { sum +=  5; cnt++; }
    if (gray & 0x80) { sum +=  7; cnt++; }

    if (cnt == 0) return 0.0f;
    return -(float)sum / cnt * gain;
}

/* 编码器采样读（读后清零）：key 模块中断累加计数，骨架按调度周期
 * （如 50ms tick）采样一次并清零，返回左右轮读数。 */
void xunji_encoder_read(int32_t *left, int32_t *right)
{
    *left = (int32_t)counter_1_A;                    // 读左轮编码器数据
    counter_1_A = 0;
    *right = (int32_t)counter_2_A;                   // 读右轮编码器数据
    counter_2_A = 0;
}

/* 电机速度输出：百分比制速度（正=前进，负=后退；0 时 duty 为 0、方向位
 * 不影响输出）→ motor 模块原始占空比 0~1300。 */
void xunji_set_speed(int left, int right)
{
    if (left > 0)  motor_set_direction(1, 1);        // 前进
    else           motor_set_direction(1, 2);        // 后退
    motor_set_duty(1, (uint32_t)((left < 0 ? -left : left) * XUNJI_MAX_DUTY / 100));

    if (right > 0) motor_set_direction(2, 1);        // 前进
    else           motor_set_direction(2, 2);        // 后退
    motor_set_duty(2, (uint32_t)((right < 0 ? -right : right) * XUNJI_MAX_DUTY / 100));
}
