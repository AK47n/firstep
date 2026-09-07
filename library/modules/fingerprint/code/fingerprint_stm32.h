/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《指纹识别传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/fingerprint-recognition-sensor.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef FINGERPRINT_STM32_H
#define FINGERPRINT_STM32_H

#include <stdint.h>

/* AS608 光学指纹识别模块驱动（stm32 纯驱动，ADR 0009）：
 * - **API 与 mspm0 fingerprint.h 同名同型完全对齐**（init/check_device/
 *   is_touched/get_image/img_to_buffer/reg_model/search/save_finger/
 *   delete_all/enroll——返回约定统一：0 = 成功、非 0 = 失败，search 返回
 *   指纹 ID（FINGERPRINT_NOT_FOUND=255））；
 * - 真实 UART（双向）：默认 **UART_1（PA9/PA10，与 K230 视觉 DIGIT_UART
 *   身份识别互替同实例同脚先例）**——57600（页面取证「as608 默认 57600」，
 *   `uart_pin_init_ex` 默认 115200 后 `uart_baud_config` 重配；市售 9600
 *   出厂版改一行即可）；同选时经引脚绑定换实例成对消解（实例上限 3）；
 * - **RX 中断聚合**：`fingerprint_rx_handler` 经母版 isr.c USARTx_IRQHandler
 *   → pin_config.h `USART1_IRQ_CALLS` 聚合宏调用（pinwriter
 *   `_UART_CALLS_ROLES` 已登记，main.c 勿写 USARTx_IRQHandler——门禁兜底）；
 *   handler 内状态机识别 6 字节帧头 0xEF 0x01 FF FF FF FF + PID/Len 大端 →
 *   **按 Len 字段精确收齐整帧**（响应帧 12 字节[确认码 [9]]、search 16 字节
 *   [10..11]=ID——页面 FPM10A_Receive_Data 的 12/16 参数语义），页面
 *   `u2_recv_length++` 无上限越界修正（缓冲 32 + 超长帧丢弃重同步）；
 * - 帧封装按页面原样：6 字节包头 + 指令段（地址/命令/参数/校验和——校验和
 *   = 指令段逐字节求和 &0xFF，页面数组原值保留；Save_Finger 页内 2 字节
 *   校验和原样）；
 * - 流程控制（先触摸→采集→比对、按键菜单）**归生成骨架（ADR 0009）**——
 *   页面 key_scanf 菜单/printf 全剔除；图像上传/下载（72K 图像缓冲传输）
 *   范围外（notes 说明）；
 * - 引脚/极性由 pin_config.h 宏与值决定（FINGERPRINT_UART/INST/
 *   TX/RX/Touch `_GPIO/_Pin`），模块代码零引脚字面量；TOUCH 默认 PB5
 *   （gpio_in 上拉——与编码器 A 相/称重/粉尘/旋钮低频重叠：指纹门禁与
 *   「带编码器闭环小车/静态称重」不同框、同选概率最低，同选经引脚绑定
 *   消解；页面 TOUCH=PA1 不照抄）。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/
 * sensor--fingerprint-recognition-sensor.md（立创 wiki 地阔星移植手册；
 * 代码按模块库规范改写：去 main.c/printf/key_scanf 菜单、中断缓冲改
 * 状态机精确收帧、函数名规范化、数组常量/校验和按页面原样）。 */

#define FINGERPRINT_RX_BUF_SIZE  32u   /* 响应帧 12/16 字节，32 留余量 */
#define FINGERPRINT_TIMEOUT_MS   1000u /* 页面 FPM10A_Receive_Data 超时（1s） */
#define FINGERPRINT_NOT_FOUND    255u  /* 搜索未找到返回（页面约定） */
#define FINGERPRINT_BAUDRATE     57600 /* AS608 出厂默认波特率（页面取证） */

/* fingerprint_init：UART 引脚/实例初始化（uart_pin_init_ex 参数化）+
 * 57600、TOUCH 输入上拉、复位 RX 状态机。uart_pin_init_ex 已使能 RX 中断
 * （本件 RX = 中断状态机精确收帧，需要）。 */
void fingerprint_init(void);

/* 返回约定（统一）：以下命令服务函数均为 0 = 成功、非 0 = 失败（超时/
 * 确认码非零）；search 例外返回指纹 ID（255 = 未找到，ID 是数据不是状态）。 */

/* 口令验证（页面 Device_Check 的 1=成功 改为统一 0=成功）：0 = 模块通信
 * 成功；非 0 = 未检测到/异常（注意接线是否正确、串口配置是否可用）。 */
uint8_t fingerprint_check_device(void);

/* 触摸检测（页面 get_as608_touch，读 TOUCH 脚）：1 = 有手指触摸识别区，
 * 0 = 无。 */
uint8_t fingerprint_is_touched(void);

/* 获得指纹图像（页面 FPM10A_Cmd_Get_Img + 确认码判定）：0 = 成功。 */
uint8_t fingerprint_get_image(void);

/* 图像转特征码存 Buffer1/Buffer2（buffer_id = 1/2）：0 = 成功。 */
uint8_t fingerprint_img_to_buffer(uint8_t buffer_id);

/* 将 Buffer1+Buffer2 合成特征模板（页面 FPM10A_Cmd_Reg_Model）：0 = 成功。 */
uint8_t fingerprint_reg_model(void);

/* 用 Buffer1 特征搜索指纹库：返回指纹 ID（0-299）；FINGERPRINT_NOT_FOUND
 * = 未找到；255 亦可由调用方与错误态区分（比对步——先采集再比对归骨架）。 */
uint16_t fingerprint_search(void);

/* 把 Buffer1 特征保存为模板（页面 FPM10A_Cmd_Save_Finger）：0 = 成功。 */
uint8_t fingerprint_save_finger(uint16_t store_id);

/* 删除指纹库全部模板（页面 FINGERPRINT_Cmd_Delete_All_Model）：0 = 成功。 */
uint8_t fingerprint_delete_all(void);

/* 录入一枚指纹（固定序列：取图→Buffer1→取图→Buffer2→合成→保存，
 * 无交互菜单——按键确认/提示节奏归生成骨架）：0 = 成功。 */
uint8_t fingerprint_enroll(uint16_t store_id);

/* RX 中断处理（母版 isr.c 经 USART1_IRQ_CALLS 聚合调用——勿在 main.c 定义） */
void fingerprint_rx_handler(void);

#endif /* FINGERPRINT_STM32_H */
