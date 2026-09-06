/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《JQ8900语音播报模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/control/jq8900-voice-broadcast-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef JQ8900_H
#define JQ8900_H

#include <stdint.h>

/* JQ8900-16P 语音播报模块驱动（mspm0 纯驱动，ADR 0009）：
 * - 软 UART 单发 TX：GPIO 位操作 9600 8N1（起始位低 → 8 数据位 LSB 先 →
 *   停止位高，每段 JQ8900_UART_BIT_US≈104us），不开 UART 外设、不占 TIMER
 *   （本批 UART 可行性调研：SysConfig CLI 拒绝同一 UART 外设多实例——
 *   "UART2 is already in use by DEBUG_UART" Resource conflict，共享不可行，
 *   语音主控→模块单向发指令帧为主，故走软 UART）；
 * - 指令帧（页面 demo {0xAA,0x06,0x00,0xB0} 实证）：0xAA + cmd + data +
 *   校验和（前三字节求和 &0xFF）；命令字按 JQ8900-16P 两线串口说明书指令表
 *   （页面仅实证 0x06 = 下一曲，其余命令字以厂家说明书/真机为准，见 manifest
 *   notes）；
 * - 页面 SendData（一线串行 APP 脚 3:1 脉宽控制）不是两线串口指令——本模块
 *   不收纳（notes 说明）；页面 UART_1_INST_IRQHandler（RX 缓冲/播放完成反馈）
 *   随软 UART 裁剪——单向 TX 无 RX，需反馈请接真实 UART 或改硬件方案。
 * 引脚 = 母版 syscfg 实例 JQ8900 / 引脚 TX（默认 PB19——DC_MOTOR 编码器 BA，
 * 语音播报与双电机小车同选概率最低，同选时经引脚绑定消解），SysConfig 配为
 * 输出、初始 SET（空闲高）。SYSCFG_DL_init() 后调 jq8900_init()。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/
 * control--jq8900-voice-broadcast-module.md（立创 wiki 地猛星移植手册；
 * 代码按模块库规范改写：UART 发送改软 UART 位操作、去 printf/main.c 演示、
 * 函数名规范化、命令帧收敛为 send_cmd + 服务函数）。 */

#define JQ8900_UART_BIT_US   104u  /* 9600 8N1 单位时间 ≈104.17us（取整 104） */

/* 命令字（JQ8900-16P 两线串口指令表；0x06 由页面 demo 实证，其余按厂家
 * 说明书命令表书写——真机/说明书核对留验证） */
#define JQ8900_CMD_PLAY_INDEX  0x01  /* 播放指定曲目（data = 曲目号） */
#define JQ8900_CMD_NEXT        0x06  /* 下一曲（页面 demo 实证） */
#define JQ8900_CMD_PREV        0x07  /* 上一曲 */
#define JQ8900_CMD_STOP        0x08  /* 停止 */
#define JQ8900_CMD_PAUSE       0x09  /* 暂停 */
#define JQ8900_CMD_RESUME      0x0A  /* 继续播放 */
#define JQ8900_CMD_SET_VOLUME  0x0B  /* 设置音量（data = 0-30） */
#define JQ8900_CMD_VOL_UP      0x0C  /* 音量 + */
#define JQ8900_CMD_VOL_DOWN    0x0D  /* 音量 - */

#define JQ8900_VOLUME_MAX      30u   /* 音量上限（0-30） */

/* jq8900_init：TX 引脚置高（空闲电平）。在 SYSCFG_DL_init() 后调用。 */
void jq8900_init(void);

/* 底层帧发送：{0xAA, cmd, data, (0xAA+cmd+data)&0xFF}，阻塞发送（~4×1040us）。 */
void jq8900_send_cmd(uint8_t cmd, uint8_t data);

/* 命令服务函数（命令字见上；jq8900_play(index) 曲目号 0-255） */
void jq8900_play(uint8_t index);
void jq8900_play_next(void);
void jq8900_play_prev(void);
void jq8900_stop(void);
void jq8900_pause(void);
void jq8900_resume(void);
void jq8900_set_volume(uint8_t volume);
void jq8900_volume_up(void);
void jq8900_volume_down(void);

#endif /* JQ8900_H */
