/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《OpenMV4摄像头》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/rf/open-mv4-camera.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef OPEN_MV4_H
#define OPEN_MV4_H

#include "ti_msp_dl_config.h"
#include <stdint.h>

/* OpenMV4 主控侧 UART 帧解析驱动（mspm0，纯驱动切片，ADR 0009）：真实
 * UART 独立实例 OPENMV4_UART（默认 UART1 = PA8(TX)/PA9(RX)——页面原接线
 * 「PA8/PA9 附加串口 1」；与 DIGIT_UART（K230 视觉）同外设同脚默认——
 * OpenMV4 与 K230 视觉互替、同选概率最低，单选裁剪后独占 UART1，同选时经
 * 引脚绑定换实例/换脚消解——批次 4 fingerprint「裁剪后独占」先例），
 * 9600（页面案例波特率）、enabledInterrupts 空 = **轮询接收**（无 ISR 强
 * 符号——fingerprint 先例）。帧格式（页面案例一/二，OpenMV Python 侧
 * `uart.write`）：`任意前缀 + [<cx>,<cy>] + \r\n`（案例一最大色块中心；
 * 页面实际发送 "Maximum color block position : [%d,%d]\r\n"）与
 * `[<pos>] + \r\n`（案例二循迹偏差单值帧，cy 置 0 占位）；案例三/四/五
 * （矩形四角 LD/RD/RU/LU、激光 [x,y]）为页面 IDE 输出或不同应用形态——
 * 本件只支持 `[数字,数字]` 与 `[数字]` 两形态，其余格式不承诺（notes）。
 * 置信度：页面帧格式无置信度字段——OpenMV 侧阈值命中才发送，取 1.0f
 * （与 coord_detect 出参 cx/cy/confidence 形态对齐，骨架消费同构）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/rf--open-mv4-camera.md
 * （立创 wiki 地猛星移植手册；主控侧 C 驱动按库规范改写：去 main.c 演示、
 * printf/HardFault_Handler、OpenMV4_usart_config 的 NVIC 使能随轮询裁剪、
 * Openmv4DataAnalysis 的「找 '[' 找 ']' 打印子串」改按行分帧 + 数值解析
 * （页面未提取整数）；页内 Python 模块代码块只作参考素材、不落码）。 */

#define OPENMV4_RX_BUF_SIZE 128u /* 行缓冲（页面 USART_RECEIVE_LENGTH 200 缩编，
                                  * 页面帧 <60 字节裕量充足） */
#define OPENMV4_CONFIDENCE   1.0f /* 页面帧无置信度字段（命中才发帧） */

/* open_mv4_init：清接收状态（页面 OpenMV4_usart_config 的 NVIC 使能随轮询
 * 裁剪——不注册中断；SYSCFG_DL_init() 已配置 UART 引脚/波特率）。 */
void open_mv4_init(void);

/* open_mv4_flush：清空分帧状态与待取帧（状态切换时调用，丢弃旧帧——坐标
 * detect 模块 flush 先例）。 */
void open_mv4_flush(void);

/* open_mv4_read_frame：排空 RX FIFO → 按行分帧（'\n' 为帧界，'\r' 忽略）
 * → 解析 `[cx,cy]`/`[pos]`；返回 0 = 新帧已解析（出参有效：cx/cy 中心坐标
 * （单值帧 cy=0）、confidence = 1.0f——页面命中帧）、1 = 暂无完整帧
 * （出参不变），坏帧（无 '['/']'、非数字、三整数越界形态）丢弃后按 1 返回。
 * 主循环节拍内调用（9600 波特 ~1.04ms/字节，排空由本函数完成）。 */
uint8_t open_mv4_read_frame(int *cx, int *cy, float *confidence);

#endif /* OPEN_MV4_H */
