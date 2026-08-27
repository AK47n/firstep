#include "headfile.h"
#include "beep_stm32.h"
#include "key_stm32.h"
#include "motor_stm32.h"
#include "ntb_time_stm32.h"

int main(void)
{
    /* 系统节拍（1ms）初始化，供 get_time_stamp_ms() 使用 */
    systick_init();

    /* 等待系统时钟稳定 */
    delay_ms(10);

    /* LED 通道初始化：红/黄/绿三个状态指示灯 */
    led_init(LED_RED);
    led_init(LED_YELLOW);
    led_init(LED_GREEN);
    led_off(LED_RED);
    led_off(LED_YELLOW);
    led_off(LED_GREEN);

    /* OLED 显示初始化 */
    OLED_Init();
    OLED_Clear();
    oled_show_text(0, 0, "Medicine Car");
    oled_show_text(1, 0, "System Ready");
    oled_refresh();

    /* 蜂鸣器初始化（用于提示音） */
    beep_init();
    beep_off();

    /* 电机与编码器初始化 */
    motor_init();
    encoder_init();

    /*
     * TODO: 按键引脚初始化
     * 若按键未在系统启动时配置，请调用 gpio_init 将对应引脚设为上拉输入。
     * 示例：gpio_init(GPIO_A, Pin_0, ID);  // 假设按键接 PA0
     */

    /*
     * TODO: 载药检测传感器初始化
     * 假设使用 GPIO/ADC/EXTI 检测药品装载到位（如 PB5）。
     * 此处应调用 adc_pin_init / gpio_init / exti_init 配置对应引脚。
     */

    /*
     * TODO: 数字识别模块（K230/UART）初始化
     * 若使用 UART 与 K230 通信，请调用 uart_init(UART_1, 115200, ...)
     * 并实现数字识别协议。
     */

    /*
     * TODO: 无线通信模块初始化（供双车协同使用）
     * 若使用 NRF24/蓝牙等，请按对应模块调用初始化函数。
     */

    while (1)
    {
        /*
         * TODO: 主状态机
         * 状态顺序：
         *   1. 等待识别病房号 + 装载药品（若未识别/未装载，保持停车）
         *   2. 识别完成且装载后，启动巡线前往病房
         *   3. 到达病房：停车，点亮红灯，等待卸载
         *   4. 卸载完成后：熄灭红灯，启动返程
         *   5. 返回药房：停车，点亮绿灯，等待下一次任务
         *
         * 可以使用 get_time_stamp_ms() 进行 20s 超时判定。
         */

        /* 示例：检测按键（可临时用于调试启动） */
        if (get_key_state() == 1)
        {
            /* TODO: 按键触发启动流程 */
        }

        /* 主循环延时，等待下一周期 */
        delay_ms(10);
    }
}
