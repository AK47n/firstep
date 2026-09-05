#ifndef FINGERPRINT_H
#define FINGERPRINT_H

#include <stdint.h>

/* AS608 光学指纹识别模块驱动（mspm0 纯驱动，ADR 0009）：
 * - 真实 UART（双向）：独立 UART 实例 FINGERPRINT_UART（默认 UART0——批次 4
 *   UART 可行性调研实证 SysConfig CLI 拒绝同一 UART 外设多实例，指纹必须双向
 *   收发故不开共享实例；默认 57600 波特（页面注释「AS608 默认 57600」——市售
 *   9600 出厂版改 syscfg 一行即可，协议与波特率无关）；**轮询接收**（页面
 *   UART_1_INST_IRQHandler + u1_recv_flag 中断缓冲改 DL_UART_isRXFIFOEmpty
 *   忙等 + 响应帧长度精确收齐，不注册 UART 中断、无 IRQHandler 强符号——
 *   同批次 2「ADC 中断改轮询（共享实例 + 中断强符号唯一性）」先例）；
 * - 帧封装按页面原样：6 字节包头 0xEF 0x01 FF FF FF FF + 指令段（地址/命令/
 *   参数/校验和——校验和 = 指令段逐字节求和 &0xFF，页面数组原值保留）；
 * - 服务函数：check_device（口令验证）/is_touched（触摸脚）/get_image/
 *   img_to_buffer(1|2)/reg_model/search/save_finger/delete_all/enroll
 *   （两次采集→合成→保存固定序列）/search（比对当前 Buffer1 特征，返回 ID）；
 *   **流程控制（先触摸→采集→比对、按键菜单 Yes/No）归生成骨架（ADR 0009）**
 *   ——页面 key_scanf 菜单/printf 全剔除；
 * - 图像上传/下载（页面 72K 图像缓冲 UART 传输）范围外（notes 说明）。
 * 引脚 = 母版 syscfg 实例：FINGERPRINT_UART（TX=PA28/RX=PA31——IMU601 原脚，
 * 身份与姿态同选概率最低、单选裁剪后独占 UART0）+ FINGERPRINT/TOUCH
 * （默认 PA12——PWMAB C0/BH1750 SCL 重叠，同选时经引脚绑定消解；模块 5 脚
 * 触摸感应输出高 = 检测到触摸，VTI 接 3.3V——直连 GPIO 即可）。
 * SYSCFG_DL_init() 后调 fingerprint_init()。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/
 * sensor--fingerprint-recognition-sensor.md（立创 wiki 地猛星移植手册；
 * 代码按模块库规范改写：去 main.c/printf/key_scanf 菜单、中断改轮询、
 * 函数名规范化、数组常量/校验和按页面原样）。 */

#define FINGERPRINT_RX_BUF_SIZE  32u   /* 响应帧 12/16 字节，32 留余量 */
#define FINGERPRINT_TIMEOUT_MS   1000u /* 页面 FPM10A_Receive_Data 超时（1s） */
#define FINGERPRINT_NOT_FOUND    255u  /* 搜索未找到返回（页面约定） */

/* fingerprint_init：清响应缓冲。在 SYSCFG_DL_init() 后调用（UART 引脚/
 * 波特率由 syscfg 配好，本函数不重配）。 */
void fingerprint_init(void);

/* 口令验证（页面 Device_Check）：返回 1 = 模块通信成功，0 = 未检测到/异常
 *（注意接线是否正确、串口配置是否可用）。 */
uint8_t fingerprint_check_device(void);

/* 触摸检测（页面 get_as608_touch）：1 = 有手指触摸识别区，0 = 无。 */
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

#endif /* FINGERPRINT_H */
