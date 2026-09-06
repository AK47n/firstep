/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《JQ8900语音播报模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/control/jq8900-voice-broadcast-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "jq8900.h"
#include "delay.h"
#include "ti_msp_dl_config.h"

/* JQ8900-16P 语音播报（mspm0 纯驱动，软 UART 单发 TX）：
 * 页内驱动（bsp_jq8900.c/h）走硬件 UART（UART_1_INST + DL_UART_*），本件按
 * 批次 4 UART 可行性调研改软 UART 位操作（9600 8N1）；页面 JQ8900_Init 只
 * 开 UART 中断（RX 缓冲/播放完成反馈），随软 UART 裁剪——本件 init 只置空闲
 * 电平；页面 SendData 是一线串行控制（GPIO APP 脚 3:1 脉宽）而非两线串口
 * 指令帧，不收纳（需要一线串行另立模块）；UART 命令帧结构按页面 demo
 * {0xAA,0x06,0x00,0xB0} 实证（0xAA + cmd + data + 校验和）。 */

/* 发送 1 位：电平 + 一个位周期（阻塞忙等，不占 TIMER） */
static void _tx_bit(uint8_t level)
{
    if (level) {
        DL_GPIO_setPins(JQ8900_PORT, JQ8900_TX_PIN);
    } else {
        DL_GPIO_clearPins(JQ8900_PORT, JQ8900_TX_PIN);
    }
    delay_us(JQ8900_UART_BIT_US);
}

/* 发送 1 字节：起始位低 → 8 数据位 LSB 先 → 停止位高（8N1） */
static void _tx_byte(uint8_t ch)
{
    uint8_t i;
    _tx_bit(0u);
    for (i = 0; i < 8; i++) {
        _tx_bit((uint8_t)((ch >> i) & 0x01u));
    }
    _tx_bit(1u);
}

void jq8900_init(void)
{
    /* 空闲高电平（SysConfig 已配初始 SET，此处再显式置一次保险） */
    DL_GPIO_setPins(JQ8900_PORT, JQ8900_TX_PIN);
}

void jq8900_send_cmd(uint8_t cmd, uint8_t data)
{
    uint8_t frame[3];
    uint8_t sum = 0;
    uint8_t i;

    frame[0] = 0xAAu;  /* 帧头 */
    frame[1] = cmd;    /* 命令字 */
    frame[2] = data;   /* 数据 */
    for (i = 0; i < 3; i++) {
        _tx_byte(frame[i]);
        sum = (uint8_t)(sum + frame[i]);
    }
    _tx_byte(sum);     /* 校验和 = 前三字节求和 &0xFF */
}

void jq8900_play(uint8_t index)
{
    jq8900_send_cmd(JQ8900_CMD_PLAY_INDEX, index);
}

void jq8900_play_next(void)
{
    jq8900_send_cmd(JQ8900_CMD_NEXT, 0x00u);
}

void jq8900_play_prev(void)
{
    jq8900_send_cmd(JQ8900_CMD_PREV, 0x00u);
}

void jq8900_stop(void)
{
    jq8900_send_cmd(JQ8900_CMD_STOP, 0x00u);
}

void jq8900_pause(void)
{
    jq8900_send_cmd(JQ8900_CMD_PAUSE, 0x00u);
}

void jq8900_resume(void)
{
    jq8900_send_cmd(JQ8900_CMD_RESUME, 0x00u);
}

void jq8900_set_volume(uint8_t volume)
{
    if (volume > JQ8900_VOLUME_MAX) {
        volume = JQ8900_VOLUME_MAX;
    }
    jq8900_send_cmd(JQ8900_CMD_SET_VOLUME, volume);
}

void jq8900_volume_up(void)
{
    jq8900_send_cmd(JQ8900_CMD_VOL_UP, 0x00u);
}

void jq8900_volume_down(void)
{
    jq8900_send_cmd(JQ8900_CMD_VOL_DOWN, 0x00u);
}
