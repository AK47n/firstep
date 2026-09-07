/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《红外解码编码模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/Infrared-decoding-coding-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "ir_remote_tx_stm32.h"
#include "pin_config.h"
#include "headfile.h"

/* NEC 帧时序（与批次 1 ir_remote 解码阈值一对一，20us 拍全落在脉宽中央） */
#define IR_TX_LEADER_LOW_US   9000u  /* 引导码：载波 */
#define IR_TX_LEADER_HIGH_US  4500u  /* 引导码：空闲（重复码 = 2250us） */
#define IR_TX_REPEAT_HIGH_US  2250u
#define IR_TX_BIT_LOW_US      560u   /* 位同步：载波 */
#define IR_TX_BIT_HIGH0_US    560u   /* 位 0：空闲 */
#define IR_TX_BIT_HIGH1_US    1680u  /* 位 1：空闲 */
#define IR_TX_STOP_US         560u   /* 帧尾：载波 */

static void ir_tx_carrier_on(void)
{
    gpio_set(IR_TX_PORT, IR_TX_OUT_PIN, 1);
}

static void ir_tx_carrier_off(void)
{
    gpio_set(IR_TX_PORT, IR_TX_OUT_PIN, 0);
}

/* 38kHz 载波 burst：半周期 ≈ 1/(2×38000) ≈ 13.16us —— stm32 无 delay_cycles
 * （mspm0 版 delay_cycles(CPUCLK_FREQ/(FREQ*2)) 先例），用 delay_us(13)
 * 忙等翻转（误差 ±0.5us、载波 ~37.8-38.5kHz，notes 记录）；**不占 TIMER**；
 * 每轮循环 = 一完整周期（一高半 + 一低半 ≈26us），周期数 = us×38000/1e6
 * （mspm0 code-review 修正公式同款——防早产放大）。
 * 宏名语义：半周期延时（mspm0 版名 IR_TX_HALF_CYCLES——按 delay_cycles
 * 换算命名；stm32 无该原语、delay_us 命名随语义改）： */
#define IR_TX_HALF_PERIOD_US() delay_us(13)

static void ir_tx_burst(uint32_t us)
{
    uint32_t cycles = (uint32_t)((uint64_t)us * IR_TX_FREQ_HZ / 1000000u);
    while (cycles > 0) {
        ir_tx_carrier_on();
        IR_TX_HALF_PERIOD_US();
        ir_tx_carrier_off();
        IR_TX_HALF_PERIOD_US();
        cycles--;
    }
}

static void ir_tx_send_bit(uint8_t bit)
{
    ir_tx_burst(IR_TX_BIT_LOW_US);
    if (bit) {
        delay_us(IR_TX_BIT_HIGH1_US);
    } else {
        delay_us(IR_TX_BIT_HIGH0_US);
    }
}

void ir_tx_init(void)
{
    gpio_init(IR_TX_PORT, IR_TX_OUT_PIN, OUT_PP); /* 推挽输出（页面配置） */
    ir_tx_carrier_off(); /* 载波空闲 = 低电平 */
}

void ir_tx_send(uint8_t address, uint8_t command)
{
    uint8_t bytes[4];
    uint8_t i;
    uint8_t bit;

    bytes[0] = address;
    bytes[1] = (uint8_t)~address; /* 地址反码 */
    bytes[2] = command;
    bytes[3] = (uint8_t)~command; /* 命令反码 */

    ir_tx_burst(IR_TX_LEADER_LOW_US); /* 引导码 9ms 载波 */
    delay_us(IR_TX_LEADER_HIGH_US);   /* 4.5ms 空闲 */

    for (i = 0; i < 4; i++) {
        for (bit = 0; bit < 8; bit++) {
#if IR_TX_MSB_FIRST
            ir_tx_send_bit((uint8_t)((bytes[i] >> (7 - bit)) & 1u));
#else
            ir_tx_send_bit((uint8_t)((bytes[i] >> bit) & 1u));
#endif
        }
    }

    ir_tx_burst(IR_TX_STOP_US); /* 结束位 */
    ir_tx_carrier_off();        /* 帧间空闲低 */
}

void ir_tx_send_repeat(void)
{
    ir_tx_burst(IR_TX_LEADER_LOW_US);
    delay_us(IR_TX_REPEAT_HIGH_US); /* 重复码空闲 2.25ms（vs 引导 4.5ms） */
    ir_tx_burst(IR_TX_STOP_US);
    ir_tx_carrier_off();
}
