/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《RC522射频IC卡识别模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/rf/rc522-rf-ic-card-identification-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#ifndef RC522_STM32_H
#define RC522_STM32_H

#include <stdint.h>

/* MFRC522 射频 IC 卡识别模块驱动（stm32，纯驱动，ADR 0009）：
 * - **软 SPI 位操作**：CS/RST/SCK/MOSI 输出 + MISO 输入（5 脚，单
 *   `RC522_PORT` 端口宏——默认全端口 B，同口约束照 ttp224 先例；**不占
 *   硬件 SPI 外设/TIMER**——照 nrf24l01 软 SPI 先例；位时序按页面
 *   200us 半周期保留，慢但稳）；
 * - **API 与 mspm0 rc522.h 现名完全对齐**：rc522_init + rc522_read_card
 *   （寻卡+防冲突出 4 字节 UID）+ rc522_auth_block/read_block/write_block
 *   （选卡→密码认证→读/写 16 字节数据块）+ rc522_halt；页面
 *   PcdRequest/PcdAnticoll/PcdSelect/PcdAuthState/PcdWrite/PcdRead/
 *   PcdComMF522/CalulateCRC 全套保留在驱动内（静态内部，服务层只包流程，
 *   流程控制归生成骨架——ADR 0009）；
 * - 返回码：RC522_OK（0x26）/RC522_NOTAGERR（0xCC）/RC522_ERR（0xBB）
 *   按页面；
 * - **上游缺陷修正**：PcdAuthState 复制序列号 `for (uc = 0; uc < 6; uc++)`
 *   应为 4 字节（页面越界读 pSnr[4..5]——按标准 MIFARE 寻钥命令 12 字节
 *   数据修正，mspm0 同）；页面上游拼写记录：CalulateCRC（应为 Calculate）、
 *   RC522_Rese（应为 Reset）——内部函数按页面原拼写保留，notes 记录。
 * 对应手册：sources/materials/lckfb-地阔星移植手册/rf--rc522-rf-ic-card-identification-module.md
 * （立创 wiki 地阔星移植手册；代码按模块库规范改写：去 main.c/printf/memset
 * 演示、函数名规范化、引脚宏参数化、F1 标准库 GPIO 换算 ml_gpio、延时走
 * 母版 ml_delay）。 */

/* 状态返回码（页面定义） */
#define RC522_OK          0x26u /* MI_OK */
#define RC522_NOTAGERR    0xCCu /* MI_NOTAGERR */
#define RC522_ERR         0xBBu /* MI_ERR */

/* 密码验证模式（页面 MIFARE 命令字） */
#define RC522_AUTH_KEYA   0x60u /* 验证 A 密钥 */
#define RC522_AUTH_KEYB   0x61u /* 验证 B 密钥 */

/* rc522_init：复位 RC522（配置常用收发模式/Timer/Auto 调制，页面
 * RC522_Rese 原样）。之后可直接 rc522_read_card（寻卡内部会开天线）。 */
void rc522_init(void);

/* 寻卡 + 防冲突：读一张卡的 4 字节 UID 到 uid[]。
 * 返回 RC522_OK / RC522_NOTAGERR / RC522_ERR；忙等时间 = 软 SPI 寄存器
 * 轮询（页面 1000 轮上限，无卡时通常 IdleIRq 早退、最坏 ~9.6s——页面原样，
 * 真机确认留验证），重试节奏由调用方决定。 */
uint8_t rc522_read_card(uint8_t uid[4]);

/* 密码认证（页面 PcdAuthState）：auth_mode = RC522_AUTH_KEYA/KEYB；
 * 认证前自动选中卡片（PcdSelect）。返回 RC522_OK / RC522_ERR。 */
uint8_t rc522_auth_block(
    uint8_t auth_mode, uint8_t block, const uint8_t key[6], const uint8_t uid[4]);

/* 读数据块（16 字节）：选卡 → 认证（KEYA）→ PcdRead。 */
uint8_t rc522_read_block(
    uint8_t block, const uint8_t key[6], const uint8_t uid[4], uint8_t data[16]);

/* 写数据块（16 字节）：选卡 → 认证（KEYA）→ PcdWrite。 */
uint8_t rc522_write_block(
    uint8_t block, const uint8_t key[6], const uint8_t uid[4], const uint8_t data[16]);

/* 让卡片进入休眠（页面 PcdHalt）。 */
void rc522_halt(void);

#endif /* RC522_STM32_H */
