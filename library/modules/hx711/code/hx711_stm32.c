/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《HX711称重传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/hx711-weighing-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "hx711_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* HX711 时序（数据手册）：DT 拉低 = 数据就绪；SCK 每脉冲串出一位（MSB 先），
 * 24 位后第 25 个脉冲切换通道 A 增益 128。SCK 周期 ≥1us。
 * 引脚：SCK 输出推挽（页面原式 Out_PP）、DT 上拉输入（页面先 PP 输出置高
 * 再重配 IPU 的动作按 mspm0 先例收敛为 init 直配 IU——页面 DT_OUT 起步置
 * 高 1us 是非必需动作，mspm0 已省；DT 就绪拉低由模块外部上拉+器件表达）。 */

/* 等 DT 就绪的时间窗：**至少一个转换周期**（driver-defect-fixes/03，两平台同款）。
 * 默认 10SPS ⇒ 一个转换周期 100ms；旧实现写 20ms（2000×10us），而
 * `hx711_init()` 内部先读一次去皮、消费掉一个采样 ⇒ 上电后紧接着的读必然超时。
 * 窗口 = 2 × 一个转换周期 = 200ms：正常路径只是在等下一个样本，不是失败；
 * 只有真没接 / 拆机（DT 恒高）才走满窗口。 */
#define HX711_SPS_DEFAULT         10u                          /* 默认输出速率（RATE 接低） */
#define HX711_CONV_PERIOD_MS      (1000u / HX711_SPS_DEFAULT)  /* 一个转换周期 = 100ms */
#define HX711_READY_TIMEOUT_MS    (HX711_CONV_PERIOD_MS * 2u)  /* 窗口 = 2 个转换周期 */
#define HX711_POLL_US             10u                          /* 轮询步长 */
#define HX711_READY_TIMEOUT_LOOPS (HX711_READY_TIMEOUT_MS * 1000u / HX711_POLL_US)

static uint32_t s_tare = 0; /* 去皮零点（计数） */

void hx711_init(void)
{
    /* 引脚配置：SCK 输出（PP）、DT 上拉输入（IU）——F1 复位后浮空输入，
     * 不初始化 = 无法驱动/采集（页面原式 PP+重配 IPU 收敛） */
    gpio_init(HX711_SCK_GPIO, HX711_SCK_PIN, OUT_PP);
    gpio_init(HX711_DT_GPIO, HX711_DT_PIN, IU);
    /* 空秤去皮：立创版 Get_Maopi 语义（走 hx711_tare 的同一处守卫）。
       这一次读会等满一个转换周期（最多 ~100ms）——那是在等第一个样本，
       不是失败。 */
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

    /* 等 DT 拉低（数据就绪；拆机/未接传感器 = 一直高，**页面 `while(DT_GET());`
     * 无界轮询主缺陷修正——按时间窗超时返回哨兵值防死等**，mspm0 同款） */
    while (gpio_get(HX711_DT_GPIO, HX711_DT_PIN)) {
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
        gpio_set(HX711_SCK_GPIO, HX711_SCK_PIN, 1);
        delay_us(1);
        count = count << 1;
        if (gpio_get(HX711_DT_GPIO, HX711_DT_PIN)) {
            count++;
        }
        gpio_set(HX711_SCK_GPIO, HX711_SCK_PIN, 0);
        delay_us(1);
    }
    /* 第 25 个脉冲：通道 A 增益 128（保持默认），**24bit 补码 → 无符号偏移量
     * （`^ 0x800000`，mspm0 同款——负重钳 0 约定）** */
    gpio_set(HX711_SCK_GPIO, HX711_SCK_PIN, 1);
    delay_us(1);
    gpio_set(HX711_SCK_GPIO, HX711_SCK_PIN, 0);
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
        return 0.0f; /* 负重量/空秤钳 0（页面 Get_Weight 语义） */
    }
    /* 克换算 = (raw - tare) / HX711_GAP_VALUE（每克计数校准除数——页面演示
     * 常数 207.00 参数化为宏，每只秤按实测调整） */
    return (float)delta / HX711_GAP_VALUE;
}
