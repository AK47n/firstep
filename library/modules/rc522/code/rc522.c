/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《RC522射频IC卡识别模块》
 * 页面：https://wiki.lckfb.com/zh-hans/dmx/module/rf/rc522-rf-ic-card-identification-module.html
 * 本代码按模块库规范改写（去演示与调试输出、函数名规范化、
 * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：
 * 标明来源与链接。 */

#include "rc522.h"
#include "delay.h"
#include "ti_msp_dl_config.h"

/* MFRC522 射频 IC 卡识别（mspm0 纯驱动，软 SPI 位操作）：
 * 页内驱动（bsp_rc522.c/h）全套保留：软 SPI 原语 + 寄存器读写族 + 基础通信
 * （天线/复位/工作方式）+ ISO14443 通信族（Pcd*）——本实现按模块库规范
 * 收敛为静态内部函数（_ 前缀）+ 对外服务函数（rc522_*）；去 main.c 演示
 * 里的 printf/memset/重复寻卡循环；引脚宏参数化（RC522_PORT +
 * RC522_<PIN>_PIN）；延时走 delay 模块（页面 200us 半周期时序保留）；
 * u8/u16/u32 宏换 stdint。**上游缺陷记录**：页面 PcdAuthState 复制序列号
 * 用 `for (uc = 0; uc < 6; uc++)`（应为 4——key 循环 6 字节的复制粘贴错，
 * 越界读 pSnr[4..5]，demo 里 ucArray_ID 只有 4 字节）——按标准 MIFARE
 * 寻钥命令（mode + block + 6 字节密钥 + 4 字节 UID = 12 字节数据）修正为
 * 4 字节；另页面拼写 CalulateCRC（应为 Calculate）/RC522_Rese（应为 Reset）
 * 属上游原文，内部函数按原拼写保留。 */

#define RC522_FIFO_MAX   18u  /* MAXRLEN：FIFO 数据上限 */

/* ---------- 软 SPI 原语（MSB 先，页 200us 半周期） ---------- */

static void _cs_low(void)  { DL_GPIO_clearPins(RC522_PORT, RC522_CS_PIN); }
static void _cs_high(void) { DL_GPIO_setPins(RC522_PORT, RC522_CS_PIN); }
static void _rst_enable(void)  { DL_GPIO_clearPins(RC522_PORT, RC522_RST_PIN); }
static void _rst_disable(void) { DL_GPIO_setPins(RC522_PORT, RC522_RST_PIN); }
static void _sck_low(void)  { DL_GPIO_clearPins(RC522_PORT, RC522_SCK_PIN); }
static void _sck_high(void) { DL_GPIO_setPins(RC522_PORT, RC522_SCK_PIN); }
static void _mosi_low(void)  { DL_GPIO_clearPins(RC522_PORT, RC522_MOSI_PIN); }
static void _mosi_high(void) { DL_GPIO_setPins(RC522_PORT, RC522_MOSI_PIN); }

static uint8_t _miso_level(void)
{
    return (DL_GPIO_readPins(RC522_PORT, RC522_MISO_PIN) & RC522_MISO_PIN) ? 1u : 0u;
}

/* 软件模拟 SPI 发送一个字节（高位先行；页面时序原样） */
static void _spi_send_byte(uint8_t byte)
{
    uint8_t n;
    for (n = 0; n < 8; n++) {
        if (byte & 0x80u) {
            _mosi_high();
        } else {
            _mosi_low();
        }
        delay_us(200);
        _sck_low();
        delay_us(200);
        _sck_high();
        delay_us(200);
        byte <<= 1;
    }
}

/* 软件模拟 SPI 读取一个字节（先读高位；页面时序原样） */
static uint8_t _spi_read_byte(void)
{
    uint8_t n;
    uint8_t data = 0;
    for (n = 0; n < 8; n++) {
        data <<= 1;
        _sck_low();
        delay_us(200);
        if (_miso_level() == 1u) {
            data |= 0x01u;
        }
        delay_us(200);
        _sck_high();
        delay_us(200);
    }
    return data;
}

/* ---------- 寄存器操作族（页面原样） ---------- */

static uint8_t _read_reg(uint8_t address)
{
    uint8_t data;
    uint8_t addr = (uint8_t)(((address << 1) & 0x7Eu) | 0x80u);
    _cs_low();
    _spi_send_byte(addr);
    data = _spi_read_byte();
    _cs_high();
    return data;
}

static void _write_reg(uint8_t address, uint8_t data)
{
    uint8_t addr = (uint8_t)((address << 1) & 0x7Eu);
    _cs_low();
    _spi_send_byte(addr);
    _spi_send_byte(data);
    _cs_high();
}

static void _set_bit_reg(uint8_t address, uint8_t mask)
{
    uint8_t temp = _read_reg(address);
    _write_reg(address, (uint8_t)(temp | mask));
}

static void _clear_bit_reg(uint8_t address, uint8_t mask)
{
    uint8_t temp = _read_reg(address);
    _write_reg(address, (uint8_t)(temp & (uint8_t)~mask));
}

/* ---------- 基础通信（天线/复位/工作方式） ---------- */

static void _antenna_on(void)
{
    uint8_t k = _read_reg(0x14); /* TxControlReg */
    if ((k & 0x03u) == 0) {
        _set_bit_reg(0x14, 0x03u);
    }
}

static void _antenna_off(void)
{
    _clear_bit_reg(0x14, 0x03u);
}

/* 复位 RC522（页面 RC522_Rese 原样：复位脚低有效脉冲，页面内部按原拼写） */
static void _reset(void)
{
    _rst_disable();  /* 空闲高 */
    delay_us(1);
    _rst_enable();   /* 复位脉冲低 */
    delay_us(1);
    _rst_disable();  /* 释放 */
    delay_us(1);
    _write_reg(0x01, 0x0Fu); /* CommandReg：复位 */
    while ((_read_reg(0x01) & 0x10u) != 0) {
        /* 等待软复位完成 */
    }
    delay_us(1);
    _write_reg(0x11, 0x3Du);  /* ModeReg：发送和接收常用模式 */
    _write_reg(0x2D, 30u);    /* TReloadRegL：16 位定时器低位 */
    _write_reg(0x2C, 0);      /* TReloadRegH：16 位定时器高位 */
    _write_reg(0x2A, 0x8Du);  /* TModeReg：内部定时器设置 */
    _write_reg(0x2B, 0x3Eu);  /* TPrescalerReg：定时器分频系数 */
    _write_reg(0x15, 0x40u);  /* TxAutoReg：调制发送信号为 100% ASK */
}

/* 设置 RC522 工作方式（页面 RC522_Config_Type：仅 ISO14443A） */
static void _config_type_a(void)
{
    _clear_bit_reg(0x08, 0x08u); /* Status2Reg：清 MFCryptol */
    _write_reg(0x11, 0x3Du);     /* ModeReg */
    _write_reg(0x17, 0x86u);     /* RxSelReg */
    _write_reg(0x26, 0x7Fu);     /* RFCfgReg */
    _write_reg(0x2D, 30u);       /* TReloadRegL */
    _write_reg(0x2C, 0);         /* TReloadRegH */
    _write_reg(0x2A, 0x8Du);     /* TModeReg */
    _write_reg(0x2B, 0x3Eu);     /* TPrescalerReg */
    delay_us(2);
    _antenna_on();
}

/* ---------- ISO14443 通信族（页面 Pcd* 全套，静态内部） ---------- */

/* 通过 RC522 和 ISO14443 卡通讯（页面 PcdComMF522 原样） */
static uint8_t _com_mf522(
    uint8_t uc_command, uint8_t *p_in_data, uint8_t uc_in_len_byte,
    uint8_t *p_out_data, uint32_t *p_out_len_bit)
{
    uint8_t status = RC522_ERR;
    uint8_t irq_en = 0x00;
    uint8_t wait_for = 0x00;
    uint8_t last_bits;
    uint8_t n;
    uint32_t ul;

    switch (uc_command) {
    case 0x0Eu: /* PCD_AUTHENT：认证 */
        irq_en = 0x12u;   /* ErrIEn + IdleIEn */
        wait_for = 0x10u; /* IdleIRq */
        break;
    case 0x0Cu: /* PCD_TRANSCEIVE：发送并接收 */
        irq_en = 0x77u;   /* TxIEn RxIEn IdleIEn LoAlertIEn ErrIEn TimerIEn */
        wait_for = 0x30u; /* RxIRq + IdleIRq */
        break;
    default:
        break;
    }

    _write_reg(0x02, (uint8_t)(irq_en | 0x80u));   /* ComIEnReg：IRqInv 置位 */
    _clear_bit_reg(0x04, 0x80u);                   /* ComIrqReg：清屏蔽位 */
    _write_reg(0x01, 0x00u);                       /* CommandReg：PCD_IDLE */
    _set_bit_reg(0x0Au, 0x80u);                    /* FIFOLevelReg：清 FIFO */

    for (ul = 0; ul < uc_in_len_byte; ul++) {
        _write_reg(0x09, p_in_data[ul]);           /* FIFODataReg：写数据 */
    }

    _write_reg(0x01, uc_command);                  /* CommandReg：写命令 */

    if (uc_command == 0x0Cu) {
        _set_bit_reg(0x0Du, 0x80u);                /* BitFramingReg：StartSend */
    }

    ul = 1000; /* 页面原样轮询上限（页面注释称 M1 卡 25ms——按软 SPI 实际位
                * 时序每轮 ~9.6ms，无卡时通常 ComIrq 的 IdleIRq 早退，最坏
                * ~9.6s；真机确认留验证） */
    do {
        n = _read_reg(0x04); /* ComIrqReg */
        ul--;
    } while ((ul != 0) && ((n & 0x01u) == 0) && ((n & wait_for) == 0));

    _clear_bit_reg(0x0Du, 0x80u); /* 清 StartSend */

    if (ul != 0) {
        if ((_read_reg(0x06) & 0x1Bu) == 0) { /* ErrorReg：BufferOvfl CollErr ParityErr ProtocolErr */
            status = RC522_OK;
            if ((n & irq_en & 0x01u) != 0) {
                status = RC522_NOTAGERR; /* 定时器中断 */
            }
            if (uc_command == 0x0Cu) {
                n = _read_reg(0x0Au);                        /* FIFOLevelReg */
                last_bits = (uint8_t)(_read_reg(0x0Cu) & 0x07u); /* ControlReg：最后字节有效位数 */
                if (last_bits != 0) {
                    *p_out_len_bit = ((uint32_t)(n - 1) * 8u) + last_bits;
                } else {
                    *p_out_len_bit = (uint32_t)n * 8u;
                }
                if (n == 0) {
                    n = 1;
                }
                if (n > RC522_FIFO_MAX) {
                    n = RC522_FIFO_MAX;
                }
                for (ul = 0; ul < n; ul++) {
                    p_out_data[ul] = _read_reg(0x09); /* FIFODataReg */
                }
            }
        } else {
            status = RC522_ERR;
        }
    } else {
        status = RC522_ERR;
    }

    _set_bit_reg(0x0Cu, 0x80u);  /* ControlReg：stop timer now */
    _write_reg(0x01, 0x00u);     /* CommandReg：PCD_IDLE */
    return status;
}

/* 寻卡（页面 PcdRequest：req_code = PICC_REQIDL/PICC_REQALL） */
static uint8_t _request(uint8_t req_code, uint8_t *tag_type)
{
    uint8_t status;
    uint8_t buf[RC522_FIFO_MAX];
    uint32_t len;

    _clear_bit_reg(0x08, 0x08u);  /* Status2Reg：清 MFCryptol */
    _write_reg(0x0Du, 0x07u);     /* BitFramingReg */
    _set_bit_reg(0x14, 0x03u);    /* TxControlReg：开天线输出 */

    buf[0] = req_code;
    status = _com_mf522(0x0Cu, buf, 1u, buf, &len);

    if ((status == RC522_OK) && (len == 0x10u)) {
        tag_type[0] = buf[0];
        tag_type[1] = buf[1];
    } else {
        status = RC522_ERR;
    }
    return status;
}

/* 防冲突（页面 PcdAnticoll：输出 4 字节序列号） */
static uint8_t _anticoll(uint8_t *snr)
{
    uint8_t status;
    uint8_t uc;
    uint8_t snr_check = 0;
    uint8_t buf[RC522_FIFO_MAX];
    uint32_t len;

    _clear_bit_reg(0x08, 0x08u);  /* Status2Reg */
    _write_reg(0x0Du, 0x00u);     /* BitFramingReg：停止收发 */
    _clear_bit_reg(0x0Eu, 0x80u); /* CollReg：清 ValuesAfterColl */

    buf[0] = 0x93u; /* 防冲突命令 */
    buf[1] = 0x20u;

    status = _com_mf522(0x0Cu, buf, 2u, buf, &len);

    if (status == RC522_OK) {
        for (uc = 0; uc < 4; uc++) {
            snr[uc] = buf[uc]; /* 读出 UID */
            snr_check = (uint8_t)(snr_check ^ buf[uc]);
        }
        if (snr_check != buf[4]) { /* buf[4] = 校验字节 */
            status = RC522_ERR;
        }
    }
    _set_bit_reg(0x0Eu, 0x80u); /* CollReg：清冲突位 */
    return status;
}

/* 用 RC522 计算 CRC16（页面 CalulateCRC——上游拼写保留） */
static void _calulate_crc(uint8_t *p_in_data, uint8_t uc_len, uint8_t *p_out_data)
{
    uint8_t uc;
    uint8_t uc_n;

    _clear_bit_reg(0x05, 0x04u); /* DivIrqReg */
    _write_reg(0x01, 0x00u);     /* CommandReg：PCD_IDLE */
    _set_bit_reg(0x0Au, 0x80u);  /* FIFOLevelReg：清 FIFO */

    for (uc = 0; uc < uc_len; uc++) {
        _write_reg(0x09, p_in_data[uc]); /* FIFODataReg */
    }
    _write_reg(0x01, 0x03u); /* CommandReg：PCD_CALCCRC */

    uc = 0xFFu;
    do {
        uc_n = _read_reg(0x05); /* DivIrqReg */
        uc--;
    } while ((uc != 0) && ((uc_n & 0x04u) == 0));

    p_out_data[0] = _read_reg(0x22); /* CRCResultRegL */
    p_out_data[1] = _read_reg(0x21); /* CRCResultRegM */
}

/* 选定卡片（页面 PcdSelect） */
static uint8_t _select(uint8_t *snr)
{
    uint8_t n;
    uint8_t uc;
    uint8_t buf[RC522_FIFO_MAX];
    uint32_t len;

    buf[0] = 0x93u; /* PICC_ANTICOLL1 */
    buf[1] = 0x70u;
    buf[6] = 0;
    for (uc = 0; uc < 4; uc++) {
        buf[uc + 2] = snr[uc];
        buf[6] = (uint8_t)(buf[6] ^ snr[uc]);
    }
    _calulate_crc(buf, 7u, &buf[7]);

    _clear_bit_reg(0x08, 0x08u); /* Status2Reg */

    n = _com_mf522(0x0Cu, buf, 9u, buf, &len);
    if ((n == RC522_OK) && (len == 0x18u)) {
        n = RC522_OK;
    } else {
        n = RC522_ERR;
    }
    return n;
}

/* 校验卡片密码（页面 PcdAuthState——**上游缺陷修正**：UID 复制 6 字节
 * 应为 4 字节，按标准 MIFARE 寻钥命令 12 字节数据） */
static uint8_t _auth_state(
    uint8_t uc_auth_mode, uint8_t uc_addr, const uint8_t *p_key, const uint8_t *p_snr)
{
    uint8_t status;
    uint8_t uc;
    uint8_t buf[RC522_FIFO_MAX];
    uint32_t len;

    buf[0] = uc_auth_mode;
    buf[1] = uc_addr;
    for (uc = 0; uc < 6; uc++) {
        buf[uc + 2] = p_key[uc];       /* 6 字节密码 */
    }
    for (uc = 0; uc < 4; uc++) {
        buf[uc + 8] = p_snr[uc];       /* 4 字节序列号（页面原 6 字节 = 越界 bug） */
    }
    status = _com_mf522(0x0Eu, buf, 12u, buf, &len);
    if ((status != RC522_OK) || ((_read_reg(0x08) & 0x08u) == 0)) {
        status = RC522_ERR;
    }
    return status;
}

/* 指定块地址写入 16 字节数据（页面 PcdWrite） */
static uint8_t _write_block_data(uint8_t uc_addr, const uint8_t *p_data)
{
    uint8_t status;
    uint8_t uc;
    uint8_t buf[RC522_FIFO_MAX];
    uint32_t len;

    buf[0] = 0xA0u; /* PICC_WRITE */
    buf[1] = uc_addr;
    _calulate_crc(buf, 2u, &buf[2]);

    status = _com_mf522(0x0Cu, buf, 4u, buf, &len);
    if ((status != RC522_OK) || (len != 4u) || ((buf[0] & 0x0Fu) != 0x0Au)) {
        status = RC522_ERR;
    }

    if (status == RC522_OK) {
        for (uc = 0; uc < 16; uc++) {
            buf[uc] = p_data[uc]; /* 要写入的 16 字节 */
        }
        _calulate_crc(buf, 16u, &buf[16]);
        status = _com_mf522(0x0Cu, buf, 18u, buf, &len);
        if ((status != RC522_OK) || (len != 4u) || ((buf[0] & 0x0Fu) != 0x0Au)) {
            status = RC522_ERR;
        }
    }
    return status;
}

/* 读取指定块地址的 16 字节数据（页面 PcdRead） */
static uint8_t _read_block_data(uint8_t uc_addr, uint8_t *p_data)
{
    uint8_t status;
    uint8_t uc;
    uint8_t buf[RC522_FIFO_MAX];
    uint32_t len;

    buf[0] = 0x30u; /* PICC_READ */
    buf[1] = uc_addr;
    _calulate_crc(buf, 2u, &buf[2]);

    status = _com_mf522(0x0Cu, buf, 4u, buf, &len);
    if ((status == RC522_OK) && (len == 0x90u)) {
        for (uc = 0; uc < 16; uc++) {
            p_data[uc] = buf[uc];
        }
    } else {
        status = RC522_ERR;
    }
    return status;
}

/* 让卡片进入休眠（页面 PcdHalt） */
static void _halt(void)
{
    uint8_t buf[RC522_FIFO_MAX];
    uint32_t len;

    buf[0] = 0x50u; /* PICC_HALT */
    buf[1] = 0;
    _calulate_crc(buf, 2u, &buf[2]);
    _com_mf522(0x0Cu, buf, 4u, buf, &len);
}

/* ---------- 对外服务函数 ---------- */

void rc522_init(void)
{
    _reset();
    _config_type_a();
}

uint8_t rc522_read_card(uint8_t uid[4])
{
    uint8_t tag_type[2];
    uint8_t status = _request(0x52u, tag_type); /* PICC_REQALL */
    if (status != RC522_OK) {
        return status;
    }
    return _anticoll(uid);
}

uint8_t rc522_auth_block(
    uint8_t auth_mode, uint8_t block, const uint8_t key[6], const uint8_t uid[4])
{
    if (_select((uint8_t *)uid) != RC522_OK) {
        return RC522_ERR;
    }
    return _auth_state(auth_mode, block, key, uid);
}

uint8_t rc522_read_block(
    uint8_t block, const uint8_t key[6], const uint8_t uid[4], uint8_t data[16])
{
    if (rc522_auth_block(RC522_AUTH_KEYA, block, key, uid) != RC522_OK) {
        return RC522_ERR;
    }
    return _read_block_data(block, data);
}

uint8_t rc522_write_block(
    uint8_t block, const uint8_t key[6], const uint8_t uid[4], const uint8_t data[16])
{
    if (rc522_auth_block(RC522_AUTH_KEYA, block, key, uid) != RC522_OK) {
        return RC522_ERR;
    }
    return _write_block_data(block, data);
}

void rc522_halt(void)
{
    _halt();
}
