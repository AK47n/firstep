/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《语音合成播报模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/control/syn6288-speech-synthesis-broadcast-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef SYN6288_H
#define SYN6288_H

#include <stdint.h>

/* SYN6288E 中文语音合成模块驱动（mspm0 纯驱动，ADR 0009）：
 * - 软 UART 单发 TX：GPIO 位操作 9600 8N1（起始位低 → 8 数据位 LSB 先 →
 *   停止位高，每段 SYN6288_UART_BIT_US≈104us），不开 UART 外设、不占 TIMER
 *   （本批 UART 可行性调研：SysConfig CLI 拒绝同一 UART 外设多实例，语音
 *   主控→模块单向发指令帧为主，故走软 UART；同 jq8900 先例）；
 * - 指令帧（按页面 bsp_syn6288.c 原样）：0xFD 帧头 + Data_Len 高低位在前
 *   （Data_Len = 文本长度 + 3）+ CmdType + CmdPar + 文本（GB2312 编码）+ 末
 *   字节异或校验（对帧头到文本逐字节 ^）；命令帧最大 206 字节，本实现文本
 *   上限 SYN6288_TEXT_MAX=200（防越界，页面 Send_Buff[210]）；
 * - 页面 SYN6288RX_BUFF / UART_1_INST_IRQHandler（状态回传 0x4A/0x41/0x45/
 *   0x4E/0x4F 缓冲）随软 UART 裁剪——单向 TX 无 RX；需接收状态回传请接真实
 *   UART 或改硬件方案（notes 说明）。
 * 引脚 = 母版 syscfg 实例 SYN6288 / 引脚 TX（默认 PB20——DC_MOTOR 编码器 BB，
 * 语音合成与双电机小车同选概率最低，且与 jq8900 默认 PB19 刻意错开（语音两
 * 件常同选），同选时经引脚绑定消解），SysConfig 配为输出、初始 SET（空闲高）。
 * SYSCFG_DL_init() 后调 syn6288_init()。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/
 * control--syn6288-speech-synthesis-broadcast-module.md（立创 wiki 地猛星
 * 移植手册；代码按模块库规范改写：UART 发送改软 UART 位操作、sprintf 去
 * stdio、去 printf/main.c 演示、函数名规范化）。 */

#define SYN6288_UART_BIT_US   104u  /* 9600 8N1 单位时间 ≈104.17us（取整 104） */
#define SYN6288_TEXT_MAX      200u  /* 文本上限（帧最大 206 字节留余量） */

/* 命令字（页面注释命令表；CmdPar 低 3 位：0=GB2312 文本、1=GBK、2=BIG5、3=UNICODE） */
#define SYN6288_CMD_SPEECH    0x01  /* 语音合成命令 */
#define SYN6288_CMD_SET_BAUD  0x31  /* 设置波特率（默认 9600） */
#define SYN6288_CMD_STOP      0x02  /* 停止合成命令 */
#define SYN6288_CMD_PAUSE     0x03  /* 暂停合成命令 */
#define SYN6288_CMD_RESUME    0x04  /* 恢复合成命令 */
#define SYN6288_CMD_QUERY     0x21  /* 芯片状态查询命令 */
#define SYN6288_CMD_SLEEP     0x88  /* 芯片进入低功耗模式 */

/* syn6288_init：TX 引脚置高（空闲电平）。在 SYSCFG_DL_init() 后调用。 */
void syn6288_init(void);

/* 底层帧发送（页面 SYN6288_Send_Cmd 原样封装，无 stdio）：
 * 0xFD + len(高/低) + cmd_type + cmd_par + text + 异或校验；text 可空
 * （stop/pause 等无文本命令）。阻塞发送。 */
void syn6288_send_cmd(uint8_t cmd_type, uint8_t cmd_par, const char *text);

/* 文本转语音播报（GB2312 文本；整段合成后模块自动播报——播完回传状态
 * 由模块侧触发，本模块无 RX 不接收，播放节奏由调用方延时控制） */
void syn6288_speak(const char *text);
void syn6288_stop(void);   /* 停止合成 */
void syn6288_pause(void);  /* 暂停合成 */
void syn6288_resume(void); /* 恢复合成 */

#endif /* SYN6288_H */
