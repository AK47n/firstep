/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《GP2Y1014AU粉尘传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/gp2y1014au-dust-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "gp2y1014au_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* GP2Y1014AU 粉尘传感器（stm32 纯驱动薄封装）：
 * - ADC 薄封装：通道 = 母版 pin_config.h 单源 GP2Y1014_AO_CH（默认
 *   ADC_Channel_5 = PA5——页面原脚：用户照页面接线即插即用）；**ADC 共享
 *   组**：本批 8 件与 flame 共读 PA5（ml_adc 的 adc_get 每次先写 SQR3 选
 *   通道再触发转换，顺序调用互不干扰——flame 先例注释确认）；同一物理脚
 *   只能接一件器件，多件同测需外部分路器/分时切换（mspm0 MEM0 共读同
 *   口径——notes 记录）；LED 驱动 GPIO 输出为器件必需例外（薄封装仅指 ADC）；
 * - LED 脉冲时序按页面原样（Read_dust_concentration：clear = LED 亮 →
 *   280us → 采样 → 40us → set = LED 关 → 9680us，周期 10ms；页面极性
 *   低有效——GPIO_WriteBit Bit_RESET = 亮）；**页面 SAMPLES 30 × 2ms ≈
 *   62ms 采样跨 LED 关断、时序本就不自洽** → 5 次快平均（us016/mspm0 先例，
 *   单次读回到 ~0.3ms 级——快平均在 280us 亮窗内完成）；
 * - 滤波 = 页面 Filter（10 点静态滑动平均，首次以首值填满窗口——页面
 *   flag_first 语义、整数截断语义保留）内嵌为模块内 static 环形缓冲
 *   （页面 Filter 全局符号泄漏收敛 static）；
 * - 换算 f = 0.17×value − 0.1（页面原式——**相对估算值非精标**：系数直接
 *   作用于 12bit ADC 码，0.17×4095−0.1 ≈ 696 超出常规 mg/m³ 量程——正文
 *   「电压-浓度线性」与公式「ADC 码-浓度线性」口径脱节；需标准粉尘标定）；
 * - LED 默认脚 = **PB5**（页面原脚 PA2 = DEBUG_UART TX 常备件不照抄；PB5
 *   叠 hx711 SCK + MOTOR_A_ENC——粉尘与称重/光电编码器闭环不同框、同选
 *   概率最低，同选经引脚绑定消解）。 */

static void gp2y1014_led_on(void)
{
    gpio_set(GP2Y1014_LED_GPIO, GP2Y1014_LED_PIN, 0); /* 页面极性：0 = 低 = LED 亮 */
}

static void gp2y1014_led_off(void)
{
    gpio_set(GP2Y1014_LED_GPIO, GP2Y1014_LED_PIN, 1);
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

    gp2y1014_led_on();                       /* LED 亮（页面 Bit_RESET） */
    delay_us(GP2Y1014_LED_SETTLE_US);        /* 280us：LED 亮后电压建立 */
    for (i = 0; i < GP2Y1014_ADC_SAMPLES; i++) {
        sum += adc_get(ADC_1, GP2Y1014_AO_CH); /* 5 次快平均（LED 亮窗口内） */
    }
    delay_us(GP2Y1014_LED_SAMPLE_TAIL_US);   /* 40us */
    gp2y1014_led_off();                      /* LED 关（页面 Bit_SET） */
    delay_us(GP2Y1014_LED_CYCLE_TAIL_US);    /* 9680us：10ms 采样周期尾段 */

    value = gp2y1014_filter((int)(sum / GP2Y1014_ADC_SAMPLES));
    return 0.17f * (float)value - 0.1f; /* 页面原式（相对估算值） */
}

void gp2y1014_init(void)
{
    gpio_init(GP2Y1014_LED_GPIO, GP2Y1014_LED_PIN, OUT_PP); /* LED 推挽输出 */
    gp2y1014_led_off(); /* LED 空闲 = 关（引脚高）；页面初始 SET 同口径 */
    /* 通道 AIN 配置 + APB2 时钟 + 6 分频 12MHz + 复位校准（ml_adc 内部完成，
     * 等效页面 Dust_GPIO_Init 流程——采样时间 239.5cyc vs 页面 55.5cyc，
     * 功能等价差异 notes 记录） */
    adc_init(ADC_1, GP2Y1014_AO_CH);
}
