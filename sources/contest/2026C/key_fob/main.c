#include "headfile.h"
#include "zigbee_uart.h"

// ============================================================
//  C题：基于无线通信的数字钥匙实验系统 — 数字钥匙端
//  主控：STM32F103C8T6
//
//  功能：
//    1. 读取 DIP-4 拨码开关 → 钥匙ID (0~15)
//    2. 通过 Zigbee DL-20 周期性发送钥匙ID给门锁端
//    3. LED 闪烁表示正常运行
//    4. DIP 变化时立即发送新ID (不等周期)
//
//  ⚠️ UWB 信标（Tag）无需 MCU 控制，上电自动广播
//     STM32 只负责 ID 发送，UWB 定位由基站独立完成
// ============================================================

// 全局毫秒计数器 (TIM2 1ms中断自增)
volatile uint32_t g_systick = 0;

// ============================================================
//  DIP-4 拨码开关读取
// ============================================================
static uint8_t dip_read(void)
{
    uint8_t val = 0;
    if (gpio_get(DIP_GPIO, DIP_PIN0) == 0) val |= 0x01;
    if (gpio_get(DIP_GPIO, DIP_PIN1) == 0) val |= 0x02;
    if (gpio_get(DIP_GPIO, DIP_PIN2) == 0) val |= 0x04;
    if (gpio_get(DIP_GPIO, DIP_PIN3) == 0) val |= 0x08;
    return val;
}

// ============================================================
//  main
// ============================================================
int main(void)
{
    uint8_t  dip_id      = 0;
    uint8_t  dip_id_prev = 0xFF;  // 初始化为无效值，确保首次发送
    uint32_t last_send   = 0;
    uint32_t last_led    = 0;
    uint8_t  led_state   = 0;

    // ---- DIP-4 引脚初始化 ----
    gpio_init(DIP_GPIO, DIP_PIN0, IU);
    gpio_init(DIP_GPIO, DIP_PIN1, IU);
    gpio_init(DIP_GPIO, DIP_PIN2, IU);
    gpio_init(DIP_GPIO, DIP_PIN3, IU);

    // ---- LED 初始化 ----
    gpio_init(LED_GPIO, LED_PIN, OUT_PP);
    gpio_set(LED_GPIO, LED_PIN, 1);  // PC13 低电平点亮，初始灭

    // ---- Zigbee DL-20 初始化 ----
    zigbee_uart_init();

    // ---- TIM2 1ms 系统滴答 ----
    tim_interrupt_ms_init(TIM_2, 1, 0);

    // ---- 主循环 ----
    while (1)
    {
        // ====== 1) 读取 DIP-4 ======
        dip_id = dip_read();

        // ====== 2) ID 变化检测 → 立即发送 ======
        if (dip_id != dip_id_prev)
        {
            zigbee_send_id(dip_id);
            dip_id_prev = dip_id;
            last_send = g_systick;  // 重置周期计时器
        }

        // ====== 3) 周期性发送 ----
        if (g_systick - last_send >= ZIGBEE_SEND_MS)
        {
            zigbee_send_id(dip_id);
            last_send = g_systick;
        }

        // ====== 4) LED 心跳闪烁 (500ms 周期) ======
        if (g_systick - last_led >= 500)
        {
            led_state = !led_state;
            gpio_set(LED_GPIO, LED_PIN, led_state ? 0 : 1);  // 低电平亮
            last_led = g_systick;
        }
    }
}
