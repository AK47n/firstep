#include "gp2y1014au.h"
#include "adc_mspm0.h" /* adc_init / adc_get：共享 ADC12_0 MEM0（薄封装） */
#include "delay.h"     /* delay_us：LED 脉冲时序（延时走库内 delay 模块） */
#include "ti_msp_dl_config.h" /* GP2Y1014_PORT / GP2Y1014_LED_PIN / CPUCLK_FREQ */

/* GP2Y1014AU 粉尘传感器（mspm0 纯驱动薄封装）：
 * - ADC 薄封装：依赖 adc 模块读 ADC12_0 MEM0 槽位（默认 PA24/A0_3）——
 *   不新开 ADC 通道；LED 驱动 GPIO 输出为器件必需例外（薄封装仅指 ADC）；
 * - LED 脉冲时序按页面原样（Read_dust_concentration：clear = LED 亮 →
 *   280us → 采样 → 40us → set = LED 关 → 9680us，周期 10ms）；页面 30 次
 *   × 2ms 平均（≈62ms，远超 10ms LED 周期——页面时序本就不自洽）改 5 次快
 *   平均（us016 快平均先例，单次读回到 ~0.3ms 级）；
 * - 滤波 = 页面 Filter（10 点静态滑动平均，首次以首值填满窗口——页面
 *   flag_first 语义、整数截断语义保留）内嵌为模块内静态环形缓冲；
 * - 换算 f = 0.17×value − 0.1（页面原式——**相对估算值非精标**）；
 * - 轮询读取，无 ADC 中断（共享 ADC12_0 实例：多模块同选时 IRQHandler 强
 *   符号须唯一，joystick/adc 先例）。 */

static void gp2y1014_led_on(void)
{
    DL_GPIO_clearPins(GP2Y1014_PORT, GP2Y1014_LED_PIN); /* 页面极性：clear = LED 亮 */
}

static void gp2y1014_led_off(void)
{
    DL_GPIO_setPins(GP2Y1014_PORT, GP2Y1014_LED_PIN);
}

/* 10 点静态滑动平均（页面 Filter 原式——内嵌：页面滤波逻辑简单（10 值环形
 * 均值），照库依赖先例取舍不依赖库内 filter 可选配套件（uwb_uart 场景）；
 * 返回 sum/窗口 整数截断（页面 `i = sum / 10.0` 对正数同语义）） */
static int gp2y1014_filter(int m)
{
    static int flag_first = 0, buff[GP2Y1014_FILTER_WINDOW], sum;
    int i;

    if (flag_first == 0) {
        flag_first = 1;
        for (i = 0, sum = 0; i < GP2Y1014_FILTER_WINDOW; i++) {
            buff[i] = m;
            sum += buff[i];
        }
        return m;
    }

    sum -= buff[0];
    for (i = 0; i < (GP2Y1014_FILTER_WINDOW - 1); i++) {
        buff[i] = buff[i + 1];
    }
    buff[GP2Y1014_FILTER_WINDOW - 1] = m;
    sum += buff[GP2Y1014_FILTER_WINDOW - 1];

    return sum / GP2Y1014_FILTER_WINDOW;
}

float gp2y1014_read_dust(void)
{
    uint32_t sum = 0;
    uint8_t i;
    int value;

    gp2y1014_led_on();                       /* LED 亮（页面 clearPins） */
    delay_us(GP2Y1014_LED_SETTLE_US);        /* 280us：LED 亮后电压建立 */
    for (i = 0; i < GP2Y1014_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, ADC_Channel_0); /* 5 次快平均（LED 亮窗口内） */
    }
    delay_us(GP2Y1014_LED_SAMPLE_TAIL_US);   /* 40us */
    gp2y1014_led_off();                      /* LED 关（页面 setPins） */
    delay_us(GP2Y1014_LED_CYCLE_TAIL_US);    /* 9680us：10ms 采样周期尾段 */

    value = gp2y1014_filter((int)(sum / GP2Y1014_ADC_SAMPLES));
    return 0.17f * (float)value - 0.1f; /* 页面原式（相对估算值） */
}

void gp2y1014_init(void)
{
    gp2y1014_led_off(); /* LED 空闲 = 关（引脚高）；SYSCFG 初始值 SET 同口径 */
    adc_init(ADC_1, ADC_Channel_0); /* 外设配置由 SYSCFG_DL_init() 完成 */
}
