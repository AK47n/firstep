/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《HX711称重传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/hx711-weighing-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "hx711.h"
#include "delay.h" /* delay_us：时序延时走库内 delay 模块（依赖已声明） */
#include "ti_msp_dl_config.h" /* HX711_PORT / HX711_HX711_SCK_PIN / HX711_DT_PIN */

/* HX711 时序（数据手册）：DT 拉低 = 数据就绪；SCK 每脉冲串出一位（MSB 先），
 * 24 位后第 25 个脉冲切换通道 A 增益 128。SCK 周期 ≥1us。 */

/* ── 等 DT 就绪的时间窗：**至少一个转换周期**（driver-defect-fixes/03）─────
 * 模块默认输出速率 10SPS（RATE 脚接低）⇒ 一个转换周期 100ms 才出一个新数据；
 * 旧实现把窗口写成 `2000 × delay_us(10)` = **20ms**（注释自己写着「20ms 超时
 * 近似手册转换周期」——那是按 80SPS 的 12.5ms 说的，默认 10SPS 不是），
 * 而 `hx711_init()` 内部就先读一次（空秤去皮）**消费掉一个采样** ⇒ 上电后
 * 紧接着的任何读都在等下一个样本、**必然超时**。
 * 现在窗口 = 2 × 一个转换周期 = 200ms：正常路径只是在「等下一个样本」，
 * 不是在失败（这正是"读之间落实节流"的等价物——驱动的等待本身覆盖了一个
 * 完整转换周期，不需要调用方自己掐时间）；只有真没接 / 拆机（DT 恒高）
 * 才会走满窗口。 */
#define HX711_SPS_DEFAULT         10u                          /* 默认输出速率（RATE 接低） */
#define HX711_CONV_PERIOD_MS      (1000u / HX711_SPS_DEFAULT)  /* 一个转换周期 = 100ms */
#define HX711_READY_TIMEOUT_MS    (HX711_CONV_PERIOD_MS * 2u)  /* 窗口 = 2 个转换周期 */
#define HX711_POLL_US             10u                          /* 轮询步长 */
#define HX711_READY_TIMEOUT_LOOPS (HX711_READY_TIMEOUT_MS * 1000u / HX711_POLL_US)

static uint32_t s_tare = 0; /* 去皮零点（计数） */

void hx711_init(void)
{
    /* 空秤去皮：立创版 Get_Maopi 语义（走 hx711_tare 的同一处守卫）。
       这一次读会**等满一个转换周期**（最多 ~100ms）——那是在等第一个样本，
       不是失败（见上面的窗口口径）。 */
    hx711_tare();
}

void hx711_tare(void)
{
    uint32_t raw = hx711_read_raw();
    if (raw != HX711_TIMEOUT_SENTINEL) {
        s_tare = raw;
    }
    /* ⚠ 没读到（哨兵）时**零点原样不动**：把 0xFFFFFFFF 存成零点会让
       `克 = (raw - tare)` 变成 raw + 1 的**天文数字**——失败必须在驱动这一层
       收住，不能指望调用方记得检查返回值。 */
}

uint32_t hx711_read_raw(void)
{
    uint32_t count = 0;
    uint8_t i;
    uint32_t timeout = 0;

    /* 等 DT 拉低（数据就绪；拆机/未接传感器 = 一直高，靠时间窗兜底防死等） */
    while (DL_GPIO_readPins(HX711_PORT, HX711_DT_PIN)) {
        delay_us(HX711_POLL_US);
        if (++timeout > HX711_READY_TIMEOUT_LOOPS) {
            /* 本次没读到：如实用**哨兵值**上报，**不用 0**——
               `count ^ 0x800000` 在空秤零点（count == 0x800000）时也返 0，
               拿 0 当失败标记就分不开「没等到数据」与「秤正好在零点」。 */
            return HX711_TIMEOUT_SENTINEL;
        }
    }
    /* 24 位读：逐位 SCK 脉冲采样 DT */
    for (i = 0; i < 24; i++) {
        DL_GPIO_setPins(HX711_PORT, HX711_HX711_SCK_PIN);
        delay_us(1);
        count = count << 1;
        if (DL_GPIO_readPins(HX711_PORT, HX711_DT_PIN)) {
            count++;
        }
        DL_GPIO_clearPins(HX711_PORT, HX711_HX711_SCK_PIN);
        delay_us(1);
    }
    /* 第 25 个脉冲：通道 A 增益 128（保持默认），24 位补码 → 无符号偏移量 */
    DL_GPIO_setPins(HX711_PORT, HX711_HX711_SCK_PIN);
    delay_us(1);
    DL_GPIO_clearPins(HX711_PORT, HX711_HX711_SCK_PIN);
    return count ^ 0x800000u;
}

float hx711_get_gram(void)
{
    uint32_t raw = hx711_read_raw();
    if (raw == HX711_TIMEOUT_SENTINEL) {
        return -1.0f; /* 本次没读到（超时）：0.0f 是「空秤 / 负重量钳 0」，
                       * 拿 0 当失败标记就分不开这两件事 */
    }
    int32_t delta = (int32_t)raw - (int32_t)s_tare;
    if (delta <= 0) {
        return 0.0f;
    }
    return (float)delta / HX711_GAP_VALUE;
}
