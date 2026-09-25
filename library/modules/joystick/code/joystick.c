/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《双轴按键摇杆模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/control/two-axis-keystroke-rocker-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "joystick.h"
#include "ti_msp_dl_config.h"

/* 双轴摇杆按键（mspm0 纯驱动）：X/Y 走 ADC12_0 MEM1/MEM2（与 adc 模块共享
 * 实例，sequence 八槽——startAdd=0 / endAdd=7，槽位 8/8 用满；MEM3 归
 * ir_distance，wiki-modules-batch2/04），SW 上拉输入低有效。
 * 轮询读取（照 adc 模块先例）；4 次快速平均降噪
 * （立创原版 30 次 × delay_ms(5) 太慢，摇杆需实时，已按库规范改造）。 */

#define JOYSTICK_ADC_MAX 4095      /* 12bit 满量程 */
#define JOYSTICK_ADC_SAMPLES 4     /* 快速平均采样次数 */

/* ── 超时判据按「时间」立，不按「自旋圈数」（driver-defect-fixes/01）────────
 * ADC12_0 是与 adc / ir_distance / 多路气体共用的 **8 槽 sequence**
 * （mspm0.syscfg：startAdd=0 / endAdd=7），每槽采样时间 125µs
 * （ADC12_0.sampleTime0 = "125 us"）⇒ 一次 startConversion 跑完整个序列
 * ≈ 8 × 125µs = 1000µs。
 * 旧实现拿「50 次寄存器轮询」当超时：50 圈只要几微秒~几十微秒，远小于
 * 1000µs ⇒ **按代码常量核算**每一轮都会在第一轮就提前判超时（这一句是常量
 * 推算；板上到底是不是「读数恒 0」**仍未上板复核**，见工单 01 的 Comments），
 * 而那一支又直接 `return 0`
 * ——0 恰好又是「杆推到端点」的合法读数，学生分不清「坏了」与「推到端点」。
 * 现在按时间等：上限 = 整次序列 × 安全系数 4 = 4000µs；轮询步长用
 * DL_Common_delayCycles 折算（它的入参是 CPU 周期，CPUCLK_FREQ 由 SysConfig
 * 生成：32MHz ⇒ 32 周期 ≈ 1µs），于是「等了多少」是时间而不是圈数。
 * 与同实例 adc 模块（无超时忙等）的口径差：adc 一次只读一件、可以无限等；
 * 摇杆要连读两轴、又会被骨架周期性调用，这里留一个「给足时间的上限」防
 * ADC 没使能时把整个骨架挂死——正常路径永远走不到上限。 */
#define JOYSTICK_ADC_SEQ_SLOTS   8u    /* mspm0.syscfg ADC12_0：endAdd - startAdd + 1 */
#define JOYSTICK_ADC_SLOT_US     125u  /* mspm0.syscfg ADC12_0.sampleTime0 = "125 us" */
#define JOYSTICK_ADC_SEQ_US      (JOYSTICK_ADC_SEQ_SLOTS * JOYSTICK_ADC_SLOT_US)
#define JOYSTICK_ADC_TIMEOUT_US  (JOYSTICK_ADC_SEQ_US * 4u) /* 安全系数 4 ⇒ 4000µs */
#define JOYSTICK_ADC_CYCLES_PER_US (CPUCLK_FREQ / 1000000u)

static uint16_t _joystick_adc_read(DL_ADC12_MEM_IDX mem)
{
    uint32_t sum = 0;
    uint32_t got_samples = 0; /* 真正采到的样本次数（超时那几圈不算） */
    for (uint32_t i = 0; i < JOYSTICK_ADC_SAMPLES; i++) {
        DL_ADC12_startConversion(ADC12_0_INST);
        uint32_t waited_us = 0;
        while (DL_ADC12_getStatus(ADC12_0_INST) & ADC12_STATUS_BUSY_ACTIVE) {
            if (waited_us >= JOYSTICK_ADC_TIMEOUT_US) {
                break; /* 这一圈超时作废——不把「没采到」当 0 记进平均 */
            }
            DL_Common_delayCycles(JOYSTICK_ADC_CYCLES_PER_US);
            waited_us++;
        }
        if (DL_ADC12_getStatus(ADC12_0_INST) & ADC12_STATUS_BUSY_ACTIVE) {
            continue; /* 本圈没等到：换下一圈再试（共 SAMPLES 圈机会） */
        }
        sum += DL_ADC12_getMemResult(ADC12_0_INST, mem);
        got_samples++;
    }
    if (got_samples == 0u) {
        return JOYSTICK_ADC_INVALID; /* 一圈都没采到：如实报「本次无效」，
                                      * 不用 0 冒充读数（0 是合法值） */
    }
    return (uint16_t)(sum / got_samples);
}

/* 原始值 → 0-100%：**唯一换算出口**。本次无效原样上报（不是 0%）——0% 是
 * 「杆推到端点」的合法读数，两者必须分得开（driver-defect-fixes/01）。 */
static uint16_t _joystick_to_percent(uint16_t raw)
{
    if (raw == JOYSTICK_ADC_INVALID) {
        return JOYSTICK_ADC_INVALID;
    }
    return (uint16_t)(((uint32_t)raw * 100u) / JOYSTICK_ADC_MAX);
}

void joystick_init(void)
{
    /* SysConfig 已配 ADC12_0（八槽 sequence）+ JOYSTICK（上拉输入），
     * 由模板 SYSCFG_DL_init() 生效；此处仅确保转换使能。 */
    DL_ADC12_enableConversions(ADC12_0_INST);
}

uint16_t joystick_read_x(void)
{
    return _joystick_adc_read(ADC12_0_ADCMEM_1);
}

uint16_t joystick_read_y(void)
{
    return _joystick_adc_read(ADC12_0_ADCMEM_2);
}

uint16_t joystick_read_x_percent(void)
{
    return _joystick_to_percent(joystick_read_x());
}

uint16_t joystick_read_y_percent(void)
{
    return _joystick_to_percent(joystick_read_y());
}

uint8_t joystick_read_sw(void)
{
    uint32_t bits = DL_GPIO_readPins(JOYSTICK_PORT, JOYSTICK_SW_PIN);
    uint8_t level = (bits & JOYSTICK_SW_PIN) ? 1 : 0;
    return (level == JOYSTICK_SW_PRESSED_LEVEL) ? 1 : 0;
}
