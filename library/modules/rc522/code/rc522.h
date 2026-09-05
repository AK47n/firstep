#ifndef RC522_H
#define RC522_H

#include <stdint.h>

/* MFRC522 射频 IC 卡识别模块驱动（mspm0 纯驱动，ADR 0009）：
 * - 软 SPI 位操作：CS/RST/SCK/MOSI 输出 + MISO 输入（5 脚，单 RC522_PORT
 *   宏；不占硬件 SPI 外设——照 nrf24l01 软 SPI 先例；位时序按页面
 *   200us 半周期保留，慢但稳）；
 * - 服务函数：rc522_init + rc522_read_card（寻卡+防冲突出 4 字节 UID）+
 *   rc522_auth_block/read_block/write_block（选卡→密码认证→读/写 16 字节
 *   数据块）+ rc522_halt；页面 PcdRequest/PcdAnticoll/PcdSelect/PcdAuthState/
 *   PcdWrite/PcdRead/PcdComMF522/CalulateCRC 全套保留在驱动内（静态内部，
 *   服务层只包流程，流程控制归生成骨架——ADR 0009）；
 * - 返回码：RC522_RESULT_OK（0x26）/MIFARE_* 状态按页面；
 * - 页面上游拼写记录：CalulateCRC（应为 Calculate）、RC522_Rese（应为
 *   Reset）——内部函数按页面原拼写保留，notes 记录。
 * 引脚 = 母版 syscfg 实例 RC522（默认 CS=PA7（DC_MOTOR BIN2 + SERVO_PWM）、
 * RST=PA18（DC_MOTOR AIN2 + MAX7219 CLK）、SCK=PA14（DCC_100_PWM2 +
 * WS2812 IN）、MOSI=PA16（编码器 AA）、MISO=PA17（编码器 AB）——读卡与
 * 车类（双电机/舵机/步进）同选概率最低，同选时经引脚绑定消解；五脚全
 * GPIOA 单口，与同批语音/指纹默认不撞）。SYSCFG_DL_init() 后调
 * rc522_init()。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/
 * rf--rc522-rf-ic-card-identification-module.md（立创 wiki 地猛星移植手册；
 * 代码按模块库规范改写：去 main.c/printf/memset 演示、函数名规范化、
 * 引脚宏参数化、延时走 delay 模块）。 */

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

#endif /* RC522_H */
