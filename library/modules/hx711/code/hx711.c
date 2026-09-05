#include "hx711.h"
#include "delay.h" /* delay_us：时序延时走库内 delay 模块（依赖已声明） */
#include "ti_msp_dl_config.h" /* HX711_PORT / HX711_SCK_PIN / HX711_DT_PIN */

/* HX711 时序（数据手册）：DT 拉低 = 数据就绪；SCK 每脉冲串出一位（MSB 先），
 * 24 位后第 25 个脉冲切换通道 A 增益 128。SCK 周期 ≥1us。 */

static uint32_t s_tare = 0; /* 去皮零点（计数） */

void hx711_init(void)
{
    s_tare = hx711_read_raw(); /* 空秤去皮：立创版 Get_Maopi 语义 */
}

void hx711_tare(void)
{
    s_tare = hx711_read_raw();
}

uint32_t hx711_read_raw(void)
{
    uint32_t count = 0;
    uint8_t i;
    uint16_t timeout = 0;

    /* 等 DT 拉低（数据就绪；拆机/未接传感器 = 一直高，超时返回 0 防死等） */
    while (DL_GPIO_readPins(HX711_PORT, HX711_DT_PIN)) {
        /* 阻塞轮询无上限会挂住生成骨架；20ms 超时近似手册转换周期 */
        delay_us(10);
        if (++timeout > 2000) {
            return 0;
        }
    }
    /* 24 位读：逐位 SCK 脉冲采样 DT */
    for (i = 0; i < 24; i++) {
        DL_GPIO_setPins(HX711_PORT, HX711_SCK_PIN);
        delay_us(1);
        count = count << 1;
        if (DL_GPIO_readPins(HX711_PORT, HX711_DT_PIN)) {
            count++;
        }
        DL_GPIO_clearPins(HX711_PORT, HX711_SCK_PIN);
        delay_us(1);
    }
    /* 第 25 个脉冲：通道 A 增益 128（保持默认），24 位补码 → 无符号偏移量 */
    DL_GPIO_setPins(HX711_PORT, HX711_SCK_PIN);
    delay_us(1);
    DL_GPIO_clearPins(HX711_PORT, HX711_SCK_PIN);
    return count ^ 0x800000u;
}

float hx711_get_gram(void)
{
    int32_t raw = (int32_t)hx711_read_raw() - (int32_t)s_tare;
    if (raw <= 0) {
        return 0.0f;
    }
    return (float)raw / HX711_GAP_VALUE;
}
