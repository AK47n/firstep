#include "motor.h"
#include "delay.h"
#include "oled.h"
#include <stdio.h>

/* 前置声明（定义在文件末尾，先声明让前面的函数能调用） */
void calculate_speed(uint8_t motor_id);
void DC_MOTOR_PID(uint8_t motor_id);
void adjust_motor_pwm(void);

float kp = 2.5; // 比例系数
float ki = 0.2; // 积分系数

int PWM_1_duty = 0;
float target_speed_1 = 0; // 目标速度 mm/s
float last_error_1 = 0;
float current_error_1 = 0;

int PWM_2_duty = 0;
float target_speed_2 = 0; // 目标速度 mm/s
float last_error_2 = 0;
float current_error_2 = 0;

extern uint32_t counter_1_A;
float speed_1 = 0;

extern uint32_t counter_2_A;
float speed_2 = 0;

// PID integral accumulators with anti-windup clamp
float integral_1 = 0;
float integral_2 = 0;
#define INTEGRAL_MAX  800
#define INTEGRAL_MIN -800

float yaw_start = 0;
extern Attitude_t current_attitude;

uint8_t task = 0;
uint8_t is_start = 0;
int64_t last_change_time = 0;

void motor_init(uint8_t motor_id)
{
    /* STBY 已改为硬件直接接 3.3V，不再由 MCU 控制 */
    if(motor_id == 1){
        // DL_Timer_startCounter(PWMAB_INST);
        DL_GPIO_setPins(DC_MOTOR_AIN1_PORT, DC_MOTOR_AIN1_PIN);
        DL_GPIO_setPins(DC_MOTOR_AIN2_PORT, DC_MOTOR_AIN2_PIN);
        DL_Timer_setCaptureCompareValue(PWMAB_INST, 0, GPIO_PWMAB_C0_IDX);
    }
    else if(motor_id == 2){
        
        DL_GPIO_setPins(DC_MOTOR_BIN1_PORT, DC_MOTOR_BIN1_PIN);
        DL_GPIO_setPins(DC_MOTOR_BIN2_PORT, DC_MOTOR_BIN2_PIN);
        DL_Timer_setCaptureCompareValue(PWMAB_INST, 0, GPIO_PWMAB_C1_IDX);
    }
    DL_Timer_startCounter(PWMAB_INST);
    DL_Timer_startCounter(MOTOR_PID_INST);
    NVIC_EnableIRQ(MOTOR_PID_INST_INT_IRQN);
}

// 电机自检：依次测试两个电机的正反转，每步运行2秒
void motor_test(void)
{
    // 启动 PWM 定时器
    DL_Timer_startCounter(PWMAB_INST);

    // === 步骤1: 电机1正转 ===
    motor_set_direction(1, 1);  // 正转
    motor_set_duty(1, 800);     // 20% 占空比
    motor_set_duty(2, 0);
    delay_ms(2000);

    // === 步骤2: 电机1反转 ===
    motor_set_direction(1, 2);  // 反转
    motor_set_duty(1, 800);
    delay_ms(2000);

    // === 步骤3: 电机1停止，电机2正转 ===
    motor_set_duty(1, 0);
    motor_set_direction(2, 1);  // 正转
    motor_set_duty(2, 800);
    delay_ms(2000);

    // === 步骤4: 电机2反转 ===
    motor_set_direction(2, 2);  // 反转
    motor_set_duty(2, 800);
    delay_ms(2000);

    // === 全部停止 ===
    motor_set_duty(1, 0);
    motor_set_duty(2, 0);
    motor_set_direction(1, 0);
    motor_set_direction(2, 0);
}

// 编码器自检：两个电机正转 5 秒，OLED 实时显示编码器计数值
void encoder_test(void)
{
    extern uint32_t counter_1_A, counter_2_A;

    // 清零计数器
    counter_1_A = 0;
    counter_2_A = 0;

    // 启动 PWM 定时器
    DL_Timer_startCounter(PWMAB_INST);

    // 两个电机同时正转
    motor_set_direction(1, 1);
    motor_set_direction(2, 1);
    motor_set_duty(1, 600);
    motor_set_duty(2, 600);

    char buf[32];
    // 每 200ms 刷新显示，共 5 秒（25 次）
    for (int i = 0; i < 25; i++)
    {
        OLED_Clear();
        OLED_ShowString(0, 0, (u8 *)"Encoder Test", 16);
        sprintf(buf, "M1: %d", (int)counter_1_A);
        OLED_ShowString(0, 20, (u8 *)buf, 16);
        sprintf(buf, "M2: %d", (int)counter_2_A);
        OLED_ShowString(0, 40, (u8 *)buf, 16);
        OLED_Refresh();
        delay_ms(200);
    }

    // 停止
    motor_set_duty(1, 0);
    motor_set_duty(2, 0);
    motor_set_direction(1, 0);
    motor_set_direction(2, 0);

    // 显示最终结果
    OLED_Clear();
    OLED_ShowString(0, 0, (u8 *)"Final Count", 16);
    sprintf(buf, "M1: %d", (int)counter_1_A);
    OLED_ShowString(0, 20, (u8 *)buf, 16);
    sprintf(buf, "M2: %d", (int)counter_2_A);
    OLED_ShowString(0, 40, (u8 *)buf, 16);
    OLED_Refresh();
    delay_ms(3000);
}

// PID 调参测试：以目标速度跑 5 秒，OLED 实时显示实际速度 vs 目标
void pid_tuning(uint16_t target_mm_s)
{
    extern uint32_t counter_1_A, counter_2_A;
    char buf[32];
    int step = 0;

    // 清空状态
    counter_1_A = 0;
    counter_2_A = 0;
    PWM_1_duty = 0;
    PWM_2_duty = 0;
    last_error_1 = 0;
    last_error_2 = 0;
    current_error_1 = 0;
    current_error_2 = 0;
    integral_1 = 0;
    integral_2 = 0;
    target_speed_1 = target_mm_s;
    target_speed_2 = target_mm_s;

    // 启动 PWM，方向正转
    DL_Timer_startCounter(PWMAB_INST);
    motor_set_direction(1, 1);
    motor_set_direction(2, 1);

    // 跑 5 秒，20Hz PID 循环（50ms 采样，脉冲够多速度才稳）
    for (step = 0; step < 100; step++)
    {
        // 先清零再延时：确保编码器只在 delay_ms(50) 期间计数
        counter_1_A = 0;
        counter_2_A = 0;
        delay_ms(50);

        // 50ms 采样 -> 脉冲 = 20Hz, 速度更稳定
        uint32_t c1 = counter_1_A;
        uint32_t c2 = counter_2_A;
        speed_1 = (float)c1 / MOTOR_BIANMAQI * PI * MOTOR_WHEEL_D * 20;
        speed_2 = (float)c2 / MOTOR_BIANMAQI * PI * MOTOR_WHEEL_D * 20;

        DC_MOTOR_PID(1);
        DC_MOTOR_PID(2);

        // 每 200ms 刷新 OLED
        if (step % 4 == 0)
        {
            OLED_Clear();
            OLED_ShowString(0, 0, (u8 *)"PID Tuning", 16);
            sprintf(buf, "k%.1f i%.1f", kp, ki);
            OLED_ShowString(64, 0, (u8 *)buf, 12);

            sprintf(buf, "T:%d mm/s", target_mm_s);
            OLED_ShowString(0, 18, (u8 *)buf, 16);

            sprintf(buf, "M1:%d", (int)speed_1);
            OLED_ShowString(0, 36, (u8 *)buf, 16);
            sprintf(buf, "M2:%d", (int)speed_2);
            OLED_ShowString(64, 36, (u8 *)buf, 16);

            sprintf(buf, "d1:%d d2:%d", PWM_1_duty, PWM_2_duty);
            OLED_ShowString(0, 54, (u8 *)buf, 12);
            OLED_Refresh();
        }
    }

    // 停止
    motor_set_duty(1, 0);
    motor_set_duty(2, 0);
    motor_set_direction(1, 0);
    motor_set_direction(2, 0);

    // 显示最终结果 3 秒
    OLED_Clear();
    OLED_ShowString(0, 0, (u8 *)"PID Result", 16);
    sprintf(buf, "kp=%.1f ki=%.1f", kp, ki);
    OLED_ShowString(0, 18, (u8 *)buf, 12);
    sprintf(buf, "T=%d mm/s", target_mm_s);
    OLED_ShowString(0, 30, (u8 *)buf, 16);
    sprintf(buf, "M1:%d M2:%d", (int)speed_1, (int)speed_2);
    OLED_ShowString(0, 48, (u8 *)buf, 16);
    OLED_Refresh();
    delay_ms(3000);
}

// 限幅函数
int limit_duty(int duty)
{
    if(duty > 1300){
        duty = 1300;
    }
    if(duty < 0){
        duty = 0;
    }
    return duty;
}

void motor_set_duty(uint8_t motor_id, uint32_t duty)
{
    duty = limit_duty(duty);
    if(motor_id == 1){
        DL_Timer_setCaptureCompareValue(PWMAB_INST, duty, GPIO_PWMAB_C0_IDX);
    }
    else if(motor_id == 2){
        DL_Timer_setCaptureCompareValue(PWMAB_INST, duty, GPIO_PWMAB_C1_IDX);
    }
}

// direction: 0 停止，1 正转，2 反转
void motor_set_direction(uint8_t motor_id, uint8_t direction)
{
    if(motor_id == 1){
        if(direction == 0){
            DL_GPIO_setPins(DC_MOTOR_AIN1_PORT, DC_MOTOR_AIN1_PIN);
            DL_GPIO_setPins(DC_MOTOR_AIN2_PORT, DC_MOTOR_AIN2_PIN);
        }
        else if(direction == 1){
            DL_GPIO_setPins(DC_MOTOR_AIN1_PORT, DC_MOTOR_AIN1_PIN);
            DL_GPIO_clearPins(DC_MOTOR_AIN2_PORT, DC_MOTOR_AIN2_PIN);
        }
        else if(direction == 2){
            DL_GPIO_clearPins(DC_MOTOR_AIN1_PORT, DC_MOTOR_AIN1_PIN);
            DL_GPIO_setPins(DC_MOTOR_AIN2_PORT, DC_MOTOR_AIN2_PIN);
        }
    }
    else if(motor_id == 2){
        if(direction == 0){
            DL_GPIO_setPins(DC_MOTOR_BIN1_PORT, DC_MOTOR_BIN1_PIN);
            DL_GPIO_setPins(DC_MOTOR_BIN2_PORT, DC_MOTOR_BIN2_PIN);
        }
        else if(direction == 1){
            DL_GPIO_setPins(DC_MOTOR_BIN1_PORT, DC_MOTOR_BIN1_PIN);
            DL_GPIO_clearPins(DC_MOTOR_BIN2_PORT, DC_MOTOR_BIN2_PIN);
        }
        else if(direction == 2){
            DL_GPIO_clearPins(DC_MOTOR_BIN1_PORT, DC_MOTOR_BIN1_PIN);
            DL_GPIO_setPins(DC_MOTOR_BIN2_PORT, DC_MOTOR_BIN2_PIN);
        }
    }
}




void calculate_speed(uint8_t motor_id)
{
    if (motor_id == 1) {
        speed_1 = (float)counter_1_A / MOTOR_BIANMAQI * PI * MOTOR_WHEEL_D * 100; // 轮速 mm/s
        counter_1_A = 0; // 计算完速度后清零计数器
    }
    if (motor_id == 2) {
        speed_2 = (float)counter_2_A / MOTOR_BIANMAQI * PI * MOTOR_WHEEL_D * 100; // 轮速 mm/s
        counter_2_A = 0; // 计算完速度后清零计数器
    }
}



void DC_MOTOR_PID(uint8_t motor_id)
{
    float error;
    if (motor_id == 1) {
        error = target_speed_1 - speed_1;
        current_error_1 = error;

        integral_1 += ki * current_error_1;
        if (integral_1 > INTEGRAL_MAX)  integral_1 = INTEGRAL_MAX;
        if (integral_1 < INTEGRAL_MIN)  integral_1 = INTEGRAL_MIN;

        PWM_1_duty = (int)(kp * current_error_1 + integral_1);
        last_error_1 = current_error_1;
        // 目标速度非零时，保证最低占空比，防止电机完全断电
        if (target_speed_1 > 0 && PWM_1_duty < 200) PWM_1_duty = 200;
        PWM_1_duty = limit_duty(PWM_1_duty);
        motor_set_duty(motor_id, PWM_1_duty);
    }
    if (motor_id == 2) {
        error = target_speed_2 - speed_2;
        current_error_2 = error;

        integral_2 += ki * current_error_2;
        if (integral_2 > INTEGRAL_MAX)  integral_2 = INTEGRAL_MAX;
        if (integral_2 < INTEGRAL_MIN)  integral_2 = INTEGRAL_MIN;

        PWM_2_duty = (int)(kp * current_error_2 + integral_2);
        last_error_2 = current_error_2;
        // 目标速度非零时，保证最低占空比，防止电机完全断电
        if (target_speed_2 > 0 && PWM_2_duty < 200) PWM_2_duty = 200;
        PWM_2_duty = limit_duty(PWM_2_duty);
        motor_set_duty(motor_id, PWM_2_duty);
    }
}

float yaw_k_p = 9.0;
int yaw_pwm_base = 0;
float yaw_k_i = 0.03;
float yaw_total_error = 0;
extern uint8_t huidu_value[];

#define status_change_counter_init 50
int status = 0; //0陀螺仪控制车头，1是巡线状态
int status_change_times = 0; // 状态切换了多少次
int status_change_counter = status_change_counter_init; // 状态切换到陀螺仪模式倒计时


int led_beep_off_counter = 30; // 关闭声光提示倒计时
float yaw_start_init = 0; // 最初车头朝向

#define MAX_PWM_DIFF 400

void adjust_head()
{
    // 360 1
    float yaw_error = current_attitude.yaw - yaw_start;
    if(yaw_error > 180) yaw_error -= 360;
    else if(yaw_error < -180) yaw_error += 360;
    int pwm_diff_half = 0;
    if(yaw_error > 0.5 || yaw_error < -0.5) pwm_diff_half = (yaw_error + yaw_total_error) * yaw_k_p;
    else yaw_total_error = 0;

    if(pwm_diff_half < -MAX_PWM_DIFF) pwm_diff_half = -MAX_PWM_DIFF;
    else if(pwm_diff_half > MAX_PWM_DIFF) pwm_diff_half = MAX_PWM_DIFF;

    motor_set_duty(1, limit_duty(yaw_pwm_base - pwm_diff_half));
    motor_set_duty(2, limit_duty(yaw_pwm_base + pwm_diff_half));
    yaw_total_error += yaw_k_i * yaw_error;
}

void MOTOR_PID_INST_IRQHandler()
{
    switch (DL_Timer_getPendingInterrupt(MOTOR_PID_INST))
    {
    case DL_TIMER_IIDX_LOAD:
        // IMU 帧超时计数（10ms/次，imu.c 收到字节时清零）
        gyro_frame_timeout++;

        if(task == 1 && is_start == 1)
        {
            yaw_pwm_base = 800;
            adjust_head();
            huidu_get_value();
            if(huidu_value[2] == 1 || huidu_value[1] == 1 || huidu_value[3] == 1)
            {
                motor_set_duty(1, 0);
                motor_set_duty(2, 0);
                is_start = 0;
                led_on();
                beep_on();
                led_beep_off_counter = 30;
            }
        }
        if(task == 2 && is_start == 1)
        {
            if(status == 0)
            {
                yaw_pwm_base = 800;
                adjust_head();
                huidu_get_value();
                if(huidu_value[2] == 1 || huidu_value[1] == 1 || huidu_value[3] == 1 || huidu_value[0] == 1 || huidu_value[4] == 1)
                {
                    if (get_time_stamp_ms() - last_change_time > 3000)
                    {
                        motor_set_duty(1, 0);
                        motor_set_duty(2, 0);
                        led_on();
                        beep_on();
                        led_beep_off_counter = 30;
                        
                        status = 1;
                        last_change_time = get_time_stamp_ms();
                        status_change_times ++;
                    }
                }
            }
            else if (status == 1)
            {
                adjust_motor_pwm();
                huidu_get_value();
                if(huidu_value[2] == 0 && huidu_value[1] == 0 && huidu_value[3] == 0 && huidu_value[0] == 0 && huidu_value[4] == 0)
                status_change_counter --;
                else status_change_counter = status_change_counter_init;
                if (status_change_counter < 0)
                {
                    if (get_time_stamp_ms() - last_change_time > 3000)
                    {
                        status = 0;
                        led_on();
                        beep_on();
                        led_beep_off_counter = 30;
                        motor_set_duty(1, 0);
                        motor_set_duty(2, 0);
                        status_change_counter = status_change_counter_init;
                        yaw_start = yaw_start + 180;
                        if(yaw_start > 360) yaw_start -= 360;
                        last_change_time = get_time_stamp_ms();
                        status_change_times ++;
                    }
                }
            }
            
            if(status_change_times == 4)
            {
                is_start = 0;
                status_change_times = 0;
                motor_set_duty(1, 0);
                motor_set_duty(2, 0);
            }
            
            
        }
        if(task == 3 && is_start == 1)
        {
            if(status == 0)
            {
                yaw_pwm_base = 800;
                adjust_head();
                huidu_get_value();
                if(huidu_value[2] == 1 || huidu_value[1] == 1 || huidu_value[3] == 1 || huidu_value[0] == 1 || huidu_value[4] == 1)
                {
                    if (get_time_stamp_ms() - last_change_time > 3000)
                    {
                        motor_set_duty(1, 0);
                        motor_set_duty(2, 0);
                        led_on();
                        beep_on();
                        led_beep_off_counter = 30;
                        
                        status = 1;
                        last_change_time = get_time_stamp_ms();
                        if (status_change_times == 0) yaw_start += 2;
                        status_change_times ++;
                    }
                }
            }
            else if (status == 1)
            {
                adjust_motor_pwm();
                huidu_get_value();
                if(huidu_value[2] == 0 && huidu_value[1] == 0 && huidu_value[3] == 0 && huidu_value[0] == 0 && huidu_value[4] == 0)
                status_change_counter --;
                else status_change_counter = status_change_counter_init;
                if (status_change_counter < 0)
                {
                    if (get_time_stamp_ms() - last_change_time > 3000)
                    {
                        status = 0;
                        led_on();
                        beep_on();
                        led_beep_off_counter = 30;
                        motor_set_duty(1, 0);
                        motor_set_duty(2, 0);
                        status_change_counter = status_change_counter_init;
                        if(status_change_times == 1) yaw_start = yaw_start + 102.8;
                        if(status_change_times == 3) yaw_start = yaw_start + 360 - 104.8;
                        if(yaw_start > 360) yaw_start -= 360;
                        last_change_time = get_time_stamp_ms();
                        status_change_times ++;
                    }
                }
            }

            
            
            if(status_change_times == 4)
            {
                is_start = 0;
                status_change_times = 0;
                motor_set_duty(1, 0);
                motor_set_duty(2, 0);
            }
            
            
        }
        if(task == 4 && is_start == 1)
        {
            if(status == 0)
            {
                yaw_pwm_base = 800;
                adjust_head();
                huidu_get_value();
                if(huidu_value[2] == 1 || huidu_value[1] == 1 || huidu_value[3] == 1 || huidu_value[0] == 1 || huidu_value[4] == 1)
                {
                    if (get_time_stamp_ms() - last_change_time > 5000)
                    {
                        motor_set_duty(1, 0);
                        motor_set_duty(2, 0);
                        led_on();
                        beep_on();
                        led_beep_off_counter = 30;
                        
                        status = 1;
                        last_change_time = get_time_stamp_ms();
                        // if (status_change_times % 4 == 0) yaw_start += 2;
                        status_change_times ++;
                    }
                }
            }
            else if (status == 1)
            {
                adjust_motor_pwm();
                huidu_get_value();
                if(huidu_value[2] == 0 && huidu_value[1] == 0 && huidu_value[3] == 0 && huidu_value[0] == 0 && huidu_value[4] == 0)
                status_change_counter --;
                else status_change_counter = status_change_counter_init;
                if (status_change_counter < 0)
                {
                    if (get_time_stamp_ms() - last_change_time > 3000)
                    {
                        status = 0;
                        led_on();
                        beep_on();
                        led_beep_off_counter = 30;
                        motor_set_duty(1, 0);
                        motor_set_duty(2, 0);
                        status_change_counter = status_change_counter_init;
                        if(status_change_times % 4 == 1) yaw_start = yaw_start_init + 102.1;
                        if(status_change_times % 4 == 3) yaw_start = yaw_start_init - 1;
                        if(yaw_start > 360) yaw_start -= 360;
                        last_change_time = get_time_stamp_ms();
                        status_change_times ++;
                    }
                }
            }
            if(status_change_times == 4 * 4)
            {
                is_start = 0;
                status_change_times = 0;
                motor_set_duty(1, 0);
                motor_set_duty(2, 0);
            }
            
            
        }
        
        if(task == 5 && is_start == 1)
        {
            adjust_motor_pwm();
        }

        led_beep_off_counter --;
        if(led_beep_off_counter < 0)
        {
            led_off();
            beep_off();
            led_beep_off_counter = 0;
        }
        // adjust_motor();
        // calculate_speed(1);
        // DC_MOTOR_PID(1);
        // calculate_speed(2);
        // DC_MOTOR_PID(2);
        break;
    // case DL_TIMER_IIDX_COMPARE_0:
    //     status = (status + 3 -1) % 3;
    //     /* code */
    //     break;

    default:
        break;
    }
}

// ============================================================
// 加权质心巡线控制（原 huidu.c，随电机驱动一并入库）
// ============================================================
// 每个传感器有固定位置权重（左负右正），检测到黑线的传感器
// 权重累加取平均，得到黑线的质心位置（连续值）。
// bias = centroid × gain，连续输出，无需穷举传感器组合。
//
// 物理排列（左→右）：L4(PA25) L3(PA24) L2(PA23) L1(PA22) R1(PA26) R2(PA27) R3(PB4) R4(PB5)
// 数组索引：              [5]     [0]     [1]    [2]    [3]     [4]     [6]     [7]
// 位置权重：              -7      -5      -3     -1     +1      +3      +5      +7
// ============================================================

/** 传感器位置权重表（按 huidu_value 索引顺序） */
static const int8_t huidu_weight[8] = {
    -5,  // [0] L3
    -3,  // [1] L2
    -1,  // [2] L1
    +1,  // [3] R1
    +3,  // [4] R2
    -7,  // [5] L4
    +5,  // [6] R3
    +7   // [7] R4
};

/**
 * 加权质心计算
 * @param gain  增益系数，值越大转弯越猛
 * @return      bias: <0 线偏左需左转, >0 线偏右需右转, =0 无线或居中
 *
 * 注意：如果实跑时发现转弯方向反了，把 gain 取负即可。
 */
static float huidu_centroid(float gain)
{
    int32_t sum = 0;
    int32_t cnt = 0;

    for (uint8_t i = 0; i < 8; i++)
    {
        if (huidu_value[i] == 1)  // 检测到黑线
        {
            sum += huidu_weight[i];
            cnt++;
        }
    }

    if (cnt == 0)
        return 0.0f;

    // bias = centroid × gain（正：线偏右→右转；负：线偏左→左转）
    return (float)sum / cnt * gain;
}

// ============================================================
// 可调参数（实跑时按需微调）
// ============================================================
#define HUIDU_BASE_SPEED    400.0f   // 直道基准速度 mm/s
#define HUIDU_GAIN_SPEED     30.0f   // 速度模式巡线增益

void adjust_motor()
{
    huidu_get_value();

    // --- 8 路全黑 → 十字/停止线，停车 ---
    if (huidu_value[0] == 1 && huidu_value[1] == 1 && huidu_value[2] == 1 && huidu_value[3] == 1 &&
        huidu_value[4] == 1 && huidu_value[5] == 1 && huidu_value[6] == 1 && huidu_value[7] == 1)
    {
        target_speed_1 = 0;
        target_speed_2 = 0;
        return;
    }

    // --- 8 路全白 → 丢线，保持原方向低速直行（等线回来） ---
    if (huidu_value[0] == 0 && huidu_value[1] == 0 && huidu_value[2] == 0 && huidu_value[3] == 0 &&
        huidu_value[4] == 0 && huidu_value[5] == 0 && huidu_value[6] == 0 && huidu_value[7] == 0)
    {
        motor_set_direction(1, 1);
        motor_set_direction(2, 1);
        float min_speed = target_speed_1 < target_speed_2 ? target_speed_1 : target_speed_2;
        target_speed_1 = min_speed;
        target_speed_2 = min_speed;
        return;
    }

    // --- 正常巡线：加权质心 → 差速分配 ---
    // bias<0: 线偏左，左轮减速右轮加速 → 左转
    // bias>0: 线偏右，右轮减速左轮加速 → 右转
    float bias = huidu_centroid(HUIDU_GAIN_SPEED);
    target_speed_1 = HUIDU_BASE_SPEED + bias;   // 左轮
    target_speed_2 = HUIDU_BASE_SPEED - bias;   // 右轮
}

// ============================================================
// PWM 差速巡线参数
// ============================================================
int pwm_huidu_base = 900;
int pwm_huidu_diff_half = 0;

#define HUIDU_GAIN_PWM   140.0f   // PWM 模式巡线增益（值越大差速越猛）

/**
 * PWM 差速巡线（加权质心版）
 *
 * 与 adjust_motor() 的区别：
 *   - adjust_motor() 输出目标速度（mm/s），由 motor.c 的 PID 做速度闭环
 *   - adjust_motor_pwm() 直接输出 PWM 占空比差速，无速度闭环
 *
 * 原理相同：加权质心 → bias → 左右轮 PWM 差速分配
 */
void adjust_motor_pwm()
{
    huidu_get_value();

    // 仅 M 亮（其余全灭）→ 居中，差速归零，直行
    if (huidu_value[0] == 0 && huidu_value[1] == 0 && huidu_value[2] == 1 && huidu_value[3] == 0 &&
        huidu_value[4] == 0 && huidu_value[5] == 0 && huidu_value[6] == 0 && huidu_value[7] == 0)
    {
        pwm_huidu_diff_half = 0;
    }
    else
    {
        // 加权质心 → 连续差速值（替代原 STEP 档位 + if-else 累加）
        float bias = huidu_centroid(HUIDU_GAIN_PWM);
        pwm_huidu_diff_half = (int)bias;
    }

    motor_set_duty(1, limit_duty(pwm_huidu_base - pwm_huidu_diff_half));
    motor_set_duty(2, limit_duty(pwm_huidu_base + pwm_huidu_diff_half));
}



