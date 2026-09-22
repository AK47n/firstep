#include "i2c_probe.h"
#include "ti_msp_dl_config.h"

/* I2C 总线原语（mspm0）：母版 SysConfig 的硬件 I2C 实例 I2C_0（`I2C_0_INST`）
 * + SDK `DL_I2C_*` 轮询控制器模式——照 ml_mpu6050 的 mpu_port.c 先例：不用
 * 中断、每个等待循环都有 `timeout` 递减出口、地址应答看状态位而不是「读回 0
 * 就算通」。SDK 符号全部封在本文件里：母版 mspm0 **一个 .h 都没有**，`DL_*`
 * 写进 main.c 会被生成门禁的未定义调用判据当场拒（工单 01 的补充说明已按
 * 实测更正）。
 *
 * 本件不写寄存器、不读数据（接口只有 init / ping / read_reg 三件事），
 * 见 i2c_probe.h 的边界说明。 */

/* 等待循环的轮数上限（照 mpu_port.c 的 100000 先例）：硬件 I2C 一次事务在
 * 400kHz 下最多几十微秒，10 万轮是数量级充足的兜底；超时即如实返回失败，
 * 不忙等死循环。 */
#define I2C_PROBE_TIMEOUT_LOOPS 100000u

/* 发起一次传输之后的沉降轮数：TI 官方示例在 startControllerTransfer 之后刻意
 * 插一段延时（示例注释 I2C_ERR_13 workaround），用意是别在状态机真正起步之前
 * 就去读状态位（否则可能读到上一次事务的残值）。示例按分频现算，本件只跑母版
 * 固定的 I2C_0 配置，取一个固定的小轮数即可（volatile 计数防止被优化掉）。 */
#define I2C_PROBE_SETTLE_LOOPS 40u

static void i2c_probe_settle(void)
{
    volatile uint32_t spin = I2C_PROBE_SETTLE_LOOPS;
    while (spin != 0u) {
        spin--;
    }
}

/* 等控制器回到空闲；0 = 已空闲 / 1 = 超时（照 mpu_port.c 的 timeout 写法）。 */
static uint8_t i2c_probe_wait_idle(void)
{
    uint32_t timeout = I2C_PROBE_TIMEOUT_LOOPS;
    while (!(DL_I2C_getControllerStatus(I2C_0_INST) &
             DL_I2C_CONTROLLER_STATUS_IDLE)) {
        if (--timeout == 0u) {
            return 1u;
        }
    }
    return 0u;
}

/* 等控制器一件事务做完（BUSY 落）；0 = 已完成 / 1 = 超时。 */
static uint8_t i2c_probe_wait_done(void)
{
    uint32_t timeout = I2C_PROBE_TIMEOUT_LOOPS;
    while (DL_I2C_getControllerStatus(I2C_0_INST) &
           DL_I2C_CONTROLLER_STATUS_BUSY) {
        if (--timeout == 0u) {
            return 1u;
        }
    }
    return 0u;
}

/* 地址相位是否被应答：0 = 有应答 / 1 = 无应答或出错。
 *
 * 判据是两个状态位：`ADDR_ACK` 必须置起，且 `ERROR` 未置起（SDK 文档原话：
 * ERROR 的来源之一就是「目标地址没有被应答」）。只看其中一个都不够——
 * 单看 ADDR_ACK 会漏掉数据相位出错，单看 ERROR 会把「没收到 ACK 位」当成功。 */
static uint8_t i2c_probe_address_nacked(void)
{
    uint32_t status = DL_I2C_getControllerStatus(I2C_0_INST);
    if ((status & DL_I2C_CONTROLLER_STATUS_ADDR_ACK) == 0u) {
        return 1u;
    }
    if (status & DL_I2C_CONTROLLER_STATUS_ERROR) {
        return 1u;
    }
    return 0u;
}

/* 从 RX FIFO 取一个字节：0 = 读到（`*value` 带回）、1 = 出错或超时。
 *
 * 两个调用点共用这一份（评审整改：原来 ping 的排干与 read_reg 的取回是两段
 * 近乎逐字重复的等待循环）：ping 只借它排干 FIFO（读回值丢弃），read_reg 用它
 * 取回寄存器值——**只有这里能把字节从总线上取下来**，两处口径不可能分家。 */
static uint8_t i2c_probe_receive_byte(uint8_t *value)
{
    uint32_t timeout = I2C_PROBE_TIMEOUT_LOOPS;
    while (DL_I2C_isControllerRXFIFOEmpty(I2C_0_INST)) {
        if (DL_I2C_getControllerStatus(I2C_0_INST) &
            DL_I2C_CONTROLLER_STATUS_ERROR) {
            return 1u;
        }
        if (--timeout == 0u) {
            return 1u;
        }
    }
    *value = DL_I2C_receiveControllerData(I2C_0_INST);
    return 0u;
}

void i2c_probe_init(void)
{
    /* 空实现占位：I2C_0 由 SYSCFG_DL_init() 按母版 mspm0.syscfg 配置好
     * （joystick / ttp224 空实现先例）。本件是总线原语不是器件驱动，没有
     * 自己的初始化序列——留这个函数只为对齐两平台 API 与给调用方一个位置。 */
}

uint8_t i2c_probe_ping(uint8_t addr7)
{
    uint8_t discarded = 0u;

    if (addr7 > 0x7Fu) {
        return 1u;
    }
    if (i2c_probe_wait_idle() != 0u) {
        return 1u;
    }
    /* START + 器件地址 + 读位，跟读 1 字节（丢弃）：**不发任何写数据字节**，
     * 器件状态零改动。选 1 字节读而不是 0 长度突发，是因为 0 长度不是本外设
     * 文档化的突发长度；读一字节严格比写一字节安全。判定只看地址应答。 */
    DL_I2C_startControllerTransfer(I2C_0_INST, addr7,
        DL_I2C_CONTROLLER_DIRECTION_RX, 1u);
    i2c_probe_settle();
    if (i2c_probe_wait_done() != 0u) {
        return 1u;
    }
    if (i2c_probe_address_nacked() != 0u) {
        return 1u;
    }
    (void)i2c_probe_receive_byte(&discarded); /* 排干 FIFO，读回值不参与判定 */
    if (i2c_probe_wait_idle() != 0u) {
        return 1u;
    }
    return 0u;
}

uint8_t i2c_probe_read_reg(uint8_t addr7, uint8_t reg, uint8_t *value)
{
    uint8_t got;

    if (value == 0) {
        return 1u;
    }
    if (addr7 > 0x7Fu) {
        return 1u;
    }
    if (i2c_probe_wait_idle() != 0u) {
        return 1u;
    }

    /* 阶段①：写寄存器指针——START + 地址(写) + 寄存器地址，**不发停止条件**
     * （STOP_DISABLE）。这是与 mpu_port.c「两段各自带停止条件」刻意偏离的一处：
     * 停止条件会让一部分器件复位寄存器指针，而本件面对的恰恰是不认识的器件。
     * 最后那个 ACK 参数按 SDK 头文件语义取「收到末字节不自动应答」（读相位用）。 */
    DL_I2C_transmitControllerData(I2C_0_INST, reg);
    DL_I2C_startControllerTransferAdvanced(I2C_0_INST, addr7,
        DL_I2C_CONTROLLER_DIRECTION_TX, 1u,
        DL_I2C_CONTROLLER_START_ENABLE, DL_I2C_CONTROLLER_STOP_DISABLE,
        DL_I2C_CONTROLLER_ACK_ENABLE);
    i2c_probe_settle();
    if (i2c_probe_wait_done() != 0u) {
        return 1u;
    }
    if (i2c_probe_address_nacked() != 0u) {
        return 1u;
    }

    /* 阶段②：重复起始 + 读地址 + 读 1 字节 + 停止 */
    DL_I2C_startControllerTransferAdvanced(I2C_0_INST, addr7,
        DL_I2C_CONTROLLER_DIRECTION_RX, 1u,
        DL_I2C_CONTROLLER_START_ENABLE, DL_I2C_CONTROLLER_STOP_ENABLE,
        DL_I2C_CONTROLLER_ACK_ENABLE);
    i2c_probe_settle();
    if (i2c_probe_wait_done() != 0u) {
        return 1u;
    }
    if (i2c_probe_address_nacked() != 0u) {
        return 1u;
    }

    if (i2c_probe_receive_byte(&got) != 0u) {
        return 1u;
    }
    if (i2c_probe_wait_idle() != 0u) {
        return 1u;
    }
    /* 只有整条事务走完才写出参：失败时 *value 原样不动（0x00 与失败两分） */
    *value = got;
    return 0u;
}
