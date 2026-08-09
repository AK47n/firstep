#include "headfile.h"

int main(void)
{
    gpio_init(GPIO_A, Pin_11, OUT_PP);
    gpio_init(GPIO_A, Pin_12, OUT_PP);
    gpio_set(GPIO_A, Pin_11, 0);  // 红灯初始熄灭
    gpio_set(GPIO_A, Pin_12, 0);  // 绿灯初始熄灭

    gray_init();
    motor_init();
    encoder_init();

    // ===== IMU初始化链（yaw_Kalman依赖，缺一不可）=====
    I2C_Init();                       // IMU软件I2C总线 (PB10=SCL, PB11=SDA)
    MPU6050_Init();                   // 唤醒陀螺仪 + 使能INT数据就绪中断(200Hz)
    HMC5883L_Init();                  // 磁力计（yaw观测源）
    exti_init(EXTI_PB7, RISING, 1);   // PB7=MPU6050 INT → EXTI7中断读数据+卡尔曼融合
                                      // 注意：最后才开中断，防止传感器未配置完就触发

    pid_init(&motorA,   POSITION_PID, 600.0f, 0, 0);
    pid_init(&motorB,   POSITION_PID, 600.0f, 0, 0);
    pid_init(&angle,    POSITION_PID, 0, 0, 0);
    pid_init(&line_pid, POSITION_PID, 1.0f, 0, 2.5f);  // PD巡线：P=1.0降推力 D=2.5强阻尼

    OLED_Init();
    OLED_Clear();
    ball_detect_init();

    // ===== 初始化PB5按键（输入上拉，按下=低电平）=====
    gpio_init(GPIO_B, Pin_5, IU);

    // ===== 等待启动画面（大字模式，2行×8字符）=====
    {
        char buf1[9], buf2[9];
        FMT8(buf1, "H: BALL");
        FMT8(buf2, "PressPB5");
        OLED_ShowStringBig(1, 1, buf1);
        OLED_ShowStringBig(2, 1, buf2);
    }

    // ===== 等待PB5按键按下启动（调试阶段：OLED实时显示K230钢珠数据）=====
    {
        uint32_t debug_refresh = 0;  // 调试刷新计数器（100ms刷新一次OLED）
        while (!car_started)
        {
            // 解析K230串口数据（UART1 ISR已接收，这里消费）
            ball_detect_parse();

            // 每100ms刷新一次OLED显示钢珠数据
            if (++debug_refresh >= 5)  // 5×20ms=100ms
            {
                debug_refresh = 0;

                char buf[9];
                static int last_cx = 0, last_cy = 0;   // 记录最后一次有效坐标
                #define LOST_THRESHOLD  3              // 连续丢3帧才显示NONE

                if (ball_result.detected)
                {
                    last_cx = ball_result.cx;
                    last_cy = ball_result.cy;
                }

                if (ball_result.lost_frames < LOST_THRESHOLD)
                {
                    // 有检测或短暂丢失 → 显示坐标（用上一次有效的值）
                    sprintf(oled_line1, "X:%d     ", last_cx);
                    FMT8(buf, oled_line1);
                    OLED_ShowStringBig(1, 1, buf);

                    sprintf(oled_line2, "Y:%d     ", last_cy);
                    FMT8(buf, oled_line2);
                    OLED_ShowStringBig(2, 1, buf);
                }
                else
                {
                    // 连续丢失≥3帧 → 显示NONE
                    FMT8(buf, "  NONE  ");
                    OLED_ShowStringBig(1, 1, buf);
                    OLED_ShowStringBig(2, 1, buf);
                }

                ball_result.updated = 0;
            }

            if (gpio_get(GPIO_B, Pin_5) == 0)  // PB5按下（低电平）
            {
                delay_ms(30);  // 消抖
                if (gpio_get(GPIO_B, Pin_5) == 0)
                {
                    car_started = 1;
                    // 等待按键抬起，防止重复触发
                    while (gpio_get(GPIO_B, Pin_5) == 0);
                    delay_ms(30);
                }
            }
            delay_ms(20);
        }
    }

    // ===== 启动10ms定时中断 =====
    tim_interrupt_ms_init(TIM_3, 10, 0);

    // =====================================================================
    //  H题主循环：刷 OLED（大字模式）
    //  所有控制逻辑在 TIM3 ISR → pid_control() 中执行
    // =====================================================================

    while (1)
    {
        if (oled_dirty) {
            OLED_ShowStringBig(1, 1, oled_line1);
            OLED_ShowStringBig(2, 1, oled_line2);
            oled_dirty = 0;
        }

        delay_ms(100);
    }
}
