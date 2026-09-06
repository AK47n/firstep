/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《红外接收模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/rf/infrared-receiving-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "ir_remote.h"
#include "delay.h"
#include "ti_msp_dl_config.h"

/* 红外遥控接收（mspm0 纯驱动，NEC 协议）：
 * - 接收头输出：无信号 = 高电平、载波脉冲 = 低电平（与手册 GET_OUT 一致）；
 * - 计时：CPU 忙等 + delay_us(20) 步进（20us 分辨率，560us 位宽约 28 拍；
 *   不占 TIMER——地猛星 TIMER 仅暴露 TIMG0/6/7/8/12 且已全占）；
 * - 触发：手册在 GROUP1_IRQHandler（下降沿）内同步解码整帧；本库改主循环
 *   轮询（等待空闲高 → 等待下降沿开始引导码 → 忙等解码）——MSPM0 全部
 *   GPIO 中断共用 GROUP1 一个向量且被 motor 编码器独占，红外+电机是经典
 *   组合、无法共存第二个 GROUP1_IRQHandler；轮询与中断解码行为等价。
 * 阈值（20us 拍）：引导码低 400-500 拍（8-10ms）/高 100-250 拍（2-5ms）、
 * 重复码高 100-150 拍（2-3ms）；位低 20-60 拍（0.4-1.2ms）；位高 60-100 拍
 * = 1（1.2-2ms）、10-50 拍 = 0（0.2-1ms）——与手册完全一致。 */

#define IR_TICK_US     20u   /* 测量步进（手册同值） */
#define IR_TIMEOUT_TICKS 500u /* 空闲/引导等待上限 10ms */

static uint8_t _level(void)
{
    return (DL_GPIO_readPins(IR_REMOTE_PORT, IR_REMOTE_OUT_PIN)
            & IR_REMOTE_OUT_PIN) ? 1 : 0;
}

static volatile uint8_t _have = 0;
static volatile uint8_t _repeat = 0;
static uint8_t _address = 0;
static uint8_t _code = 0;

/* 测量电平持续拍数（20us/拍）；超时返回 max_ticks+1（阈值都按 >max 判错，
 * 超时不落进合法区间）。 */
static uint16_t _measure(uint8_t want, uint16_t max_ticks)
{
    uint16_t ticks = 0;
    while (_level() == want) {
        delay_us(IR_TICK_US);
        if (++ticks > max_ticks) {
            return (uint16_t)(max_ticks + 1);
        }
    }
    return ticks;
}

void ir_remote_init(void)
{
    _have = 0;
    _repeat = 0;
    _address = 0;
    _code = 0;
}

uint8_t ir_remote_poll(void)
{
    uint16_t ticks;
    uint16_t low;
    uint16_t high;
    uint8_t value[4];
    uint8_t group;
    uint8_t bit;

    /* 等待空闲（高）——信号无/帧间隙时返回 0（最多等 10ms） */
    ticks = 0;
    while (_level() == 0) {
        delay_us(IR_TICK_US);
        if (++ticks > IR_TIMEOUT_TICKS) {
            return 0;
        }
    }
    /* 等待下降沿（引导码开始）——无遥控信号时最多等 10ms */
    ticks = 0;
    while (_level() == 1) {
        delay_us(IR_TICK_US);
        if (++ticks > IR_TIMEOUT_TICKS) {
            return 0;
        }
    }

    /* 引导码：低 8-10ms */
    low = _measure(0, 500);
    if (low < 400 || low > 500) {
        return 0;
    }
    /* 高 2-5ms；2-3ms = 重复码 */
    high = _measure(1, 250);
    if (high < 100 || high > 250) {
        return 0;
    }
    if (high > 100 && high < 150) {
        _repeat = 1;
        _have = 1;
        return 2; /* 重复码：上一帧代码不变 */
    }

    /* 4 组字节：地址码 + 地址反码 + 命令码 + 命令反码（MSB 先） */
    for (group = 0; group < 4; group++) {
        value[group] = 0;
        for (bit = 0; bit < 8; bit++) {
            low = _measure(0, 60);
            if (low < 20 || low > 60) {
                return 0; /* 位间隔不在 0.56ms 附近 */
            }
            high = _measure(1, 100);
            if (high >= 60 && high < 100) {
                value[group] = (uint8_t)((value[group] << 1) | 1u);
            } else if (high >= 10 && high < 50) {
                value[group] = (uint8_t)((value[group] << 1) | 0u);
            } else {
                return 0; /* 位高电平不在 0/1 码窗口内（手册此处沿用上一 bit
                           * 值不判错；实现按整帧失败处理，更严——见 notes） */
            }
        }
    }

    /* 反码校验：地址/命令各带反码（原版 infrared_data_true_judgment 判定
     * 逻辑错乱——命令反码不等时返回 1 却仍落库，已修正为严格校验） */
    if ((uint8_t)~value[1] != value[0]) {
        return 0;
    }
    if ((uint8_t)~value[3] != value[2]) {
        return 0;
    }

    _address = value[0];
    _code = value[2];
    _have = 1;
    _repeat = 0;
    return 1;
}

uint8_t ir_remote_get_address(void)
{
    return _address;
}

uint8_t ir_remote_get_code(void)
{
    return _code;
}

uint8_t ir_remote_has_data(void)
{
    return (_have || _repeat) ? 1 : 0;
}

void ir_remote_clear(void)
{
    _have = 0;
    _repeat = 0;
}
