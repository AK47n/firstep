/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《语音合成播报模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/control/syn6288-speech-synthesis-broadcast-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "syn6288.h"
#include "delay.h"
#include "ti_msp_dl_config.h"

/* SYN6288E 中文语音合成（mspm0 纯驱动，软 UART 单发 TX）：
 * 页内驱动（bsp_syn6288.c/h）走硬件 UART（UART_1_INST + DL_UART_*），本件按
 * 批次 4 UART 可行性调研改软 UART 位操作（9600 8N1）；页面 SYN6288_Init 只
 * 开 UART 中断（RX 状态回传缓冲），随软 UART 裁剪——本件 init 只置空闲电平；
 * 帧封装按页面 SYN6288_Send_Cmd 原样（0xFD + Data_Len(文本+3) + 命令字 +
 * 参数 + 文本 + 异或校验），sprintf 去 stdio 改流式逐字节发送。 */

/* 发送 1 位：电平 + 一个位周期（阻塞忙等，不占 TIMER） */
static void _tx_bit(uint8_t level)
{
    if (level) {
        DL_GPIO_setPins(SYN6288_PORT, SYN6288_TX_PIN);
    } else {
        DL_GPIO_clearPins(SYN6288_PORT, SYN6288_TX_PIN);
    }
    delay_us(SYN6288_UART_BIT_US);
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

void syn6288_init(void)
{
    /* 空闲高电平（SysConfig 已配初始 SET，此处再显式置一次保险） */
    DL_GPIO_setPins(SYN6288_PORT, SYN6288_TX_PIN);
}

void syn6288_send_cmd(uint8_t cmd_type, uint8_t cmd_par, const char *text)
{
    uint16_t text_len = 0;
    uint16_t data_len;
    uint8_t frame_head[5];
    uint8_t xor_check = 0;
    uint16_t i;

    if (text) {
        while (text[text_len] && text_len < SYN6288_TEXT_MAX) {
            text_len++;
        }
    }
    data_len = (uint16_t)(text_len + 3u); /* 页面 Data_Len = 文本长度 + 3 */

    frame_head[0] = 0xFDu;                        /* 帧头 */
    frame_head[1] = (uint8_t)(data_len >> 8);     /* 数据长度高位在前 */
    frame_head[2] = (uint8_t)(data_len & 0x00FF); /* 数据长度低位在前 */
    frame_head[3] = cmd_type;                     /* 命令字 */
    frame_head[4] = cmd_par;                      /* 命令参数 */

    for (i = 0; i < 5; i++) {
        xor_check = (uint8_t)(xor_check ^ frame_head[i]);
        _tx_byte(frame_head[i]);
    }
    for (i = 0; i < text_len; i++) {
        uint8_t ch = (uint8_t)text[i];
        xor_check = (uint8_t)(xor_check ^ ch);
        _tx_byte(ch);
    }
    _tx_byte(xor_check); /* 异或校验最后发送（页面原样） */
}

void syn6288_speak(const char *text)
{
    syn6288_send_cmd(SYN6288_CMD_SPEECH, 0x00u, text);
}

void syn6288_stop(void)
{
    syn6288_send_cmd(SYN6288_CMD_STOP, 0x00u, NULL);
}

void syn6288_pause(void)
{
    syn6288_send_cmd(SYN6288_CMD_PAUSE, 0x00u, NULL);
}

void syn6288_resume(void)
{
    syn6288_send_cmd(SYN6288_CMD_RESUME, 0x00u, NULL);
}
