/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《NEO-6M GPS模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/neo-6m-gps-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef NEO_6M_STM32_H
#define NEO_6M_STM32_H

#include <stdint.h>

/* NEO-6M GPS 定位模块驱动（stm32 纯驱动，B 类——仅 stm32 条目、无 mspm0
 * 对照，ADR 0009）：
 * - **真实串口 9600 + NMEA 帧识别**（页面代码形态：`$`→GPRMC→`\n` 帧识别 +
 *   **主循环字段解析**（页面 parseGpsBuffer 在 main 循环——本件解析收敛为
 *   get_position 服务函数）；非 AT 透传——NEO-6M 无 AT（ubx 配置范围外）：
 * - **RX 中断收帧**：neo_6m_rx_handler（母版 isr.c USARTx_IRQHandler →
 *   pin_config.h `USART1_IRQ_CALLS` 聚合宏调用——pinwriter
 *   `_UART_CALLS_ROLES` 已登记，main.c 勿写 USARTx_IRQHandler）在收到 `$`
 *   时开始新帧、按字节收满缓冲、`\n` 行尾校验帧头 GPRMC/GNRMC 后入帧存储
 *   + 置位；**缺陷修正**：① 页面 `GPSRX_LEN=255` 后 `GPSRX_BUFF[GPSRX_LEN++]`
 *   **下标 255 越界** → 本件接收缓冲 256 + **截断保护**（超长帧丢弃）；
 *   ② 页面 `memcpy(Save_Data.GPS_Buffer, ...)` 80 字节缓冲**无长度检查**
 *   → 本件拷贝截断到 NEO_6M_FRAME_BUF_SIZE-1；③ 帧头只验 `[4]=='M'&&[5]=='C'`
 *   未验语句 ID 全串 → 本件验 `$`+GP|GN RMC 全串；
 * - **定位换算**：GPRMC 字段 3/4（纬度 ddmm.mmmm、N/S）与 5/6（经度
 *   dddmm.mmmm、E/W）→ `neo_6m_get_position` 输出**十进制度**（dd+mm.mmmm/60，
 *   N=+ S=-、E=+ W=-）；页面原样字符串字段、不做 ddmm→ddd 换算是范围外
 *   （页面输出是字符串——本件按 spec 定稿做换算）；日期/时间/速度字段
 *   不解析（范围外，notes）；
 * - NMEA `*XX` 校验和/坏帧静默（页面无校验——范围外）；定位时间 = 器件
 *   首次定位（室外/星历/温启动——页面注释范围外）。
 * 引脚/极性由 pin_config.h 宏与值决定（NEO_6M_UART/INST/TX/RX `_GPIO/_Pin`），
 * 模块代码零引脚字面量；默认 **UART_1（PA9/PA10）**——与 UWB 定位链路
 * **互替件同脚先例**（GPS 室外定位 × UWB 室内定位——互替同脚先例：
 * as32×zigbee/hc05×uwb），同选经引脚绑定换实例成对消解。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/rf--neo-6m-gps-module.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：中断收帧改状态机 +
 * 截断修正、解析收敛 get_position、去 main.c 演示/errorLog 死循环/printf、
 * 函数名规范化、引脚宏参数化）。 */

#define NEO_6M_RX_BUF_SIZE      256u  /* 接收缓冲（页面 255 越界修正——+1 余量） */
#define NEO_6M_FRAME_BUF_SIZE   80u   /* 完整 GPRMC 帧存储（页面 GPS_Buffer[80]） */
#define NEO_6M_BAUDRATE         9600  /* NEO-6M 出厂默认（页面） */

/* neo_6m_init：UART 引脚/实例初始化（uart_pin_init_ex 参数化）+ 9600、
 * 复位收帧状态。uart_pin_init_ex 已使能 RX 中断（本件 RX = 中断收帧，需要）。 */
void neo_6m_init(void);

/* 帧检测：返回 1 = 自上次读取后收到一条完整 GPRMC/GNRMC 帧（并标记已读）；
 * 0 = 无新帧。帧数据由 neo_6m_get_position 解析（日期/时间/速度字段不解析）。 */
uint8_t neo_6m_read_frame(void);

/* 位置解析（GPRMC 字段 3/4/5/6）：输出十进制度（ddmm.mmmm → dd+mm/60，
 * 纬度 N=+ S=-、经度 E=+ W=-）。返回：0 = 解析成功；1 = 无新帧（未收到）；
 * 2 = 数据无效（状态位 V/字段缺失）。按调用方语义：先 read_frame 再取位置。 */
uint8_t neo_6m_get_position(float *lat, float *lon);

/* 清空收帧状态（缓冲/标志/帧存储）。 */
void neo_6m_clear(void);

/* RX 中断处理（母版 isr.c 经 USART1_IRQ_CALLS 聚合调用——勿在 main.c 定义） */
void neo_6m_rx_handler(void);

#endif /* NEO_6M_STM32_H */
