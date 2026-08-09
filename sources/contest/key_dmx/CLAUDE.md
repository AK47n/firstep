# CLAUDE.md — MSPM0G3507 数字钥匙端（信标端）

> **平台**：TI MSPM0G3507 (Cortex-M0+) | CCS Theia | DriverLib
> **项目类型**：数字钥匙信标端，DIP 拨码 ID + DL-20 ZigBee 透传

---

## 项目结构

```
├── empty.syscfg              # TI SysConfig 引脚/外设配置
├── main.c                    # 固件主程序
├── ti_msp_dl_config.h/c      # SysConfig 自动生成（勿手动改）
├── KEY_SPEC.md               # 钥匙方案规格
└── CLAUDE.md                 # 本文件
```

---

## 关键文档

| 文档 | 路径 | 用途 |
|------|------|------|
| 钥匙方案规格 | [KEY_SPEC.md](KEY_SPEC.md) | **最重要！** 接线、数据帧格式、DIP 读取规则、伪代码 |

---

## 引脚分配

| 引脚 | 功能 | 方向 | 说明 |
|------|------|------|------|
| **PB6** | UART1 TX | 输出 | → DL-20 RXD |
| **PB7** | UART1 RX | 输入 | ← DL-20 TXD（只发不收，RX 仅初始化） |
| **PA12** | DIP bit0 | 上拉输入 | 第1位（最左），ON=读到0=该位为1，对应 ID 0x01 (LSB) |
| **PA13** | DIP bit1 | 上拉输入 | 第2位，对应 ID 0x02 |
| **PA14** | DIP bit2 | 上拉输入 | 第3位，对应 ID 0x04 |
| **PA15** | DIP bit3 | 上拉输入 | 第4位（最右），对应 ID 0x08 (MSB) |

---

## 数据帧格式（4 字节，不可修改）

| 字节 | 内容 | 说明 |
|------|------|------|
| [0] | 0xAA | 同步头1 |
| [1] | 0x55 | 同步头2 |
| [2] | ID | 钥匙 ID = DIP 拨码值（0x00～0x0F） |
| [3] | SUM | 校验和 = `(0xAA + 0x55 + ID) & 0xFF` |

每 100ms 发送一帧，持续发送，永不停止。

---

## 程序逻辑

```
上电 → SYSCFG_DL_init() → SysTick_Config(1ms)

主循环（每 100ms）：
  1. 读 PA12~PA15（ON=0→bit=1，OFF=1→bit=0）
  2. id = bit0 | bit1 | bit2 | bit3  （取低4位）
  3. sum = (0xAA + 0x55 + id) & 0xFF
  4. 串口发送 AA → 55 → id → sum
```

---

## 串口参数

- **外设**：UART1，PB6(TX) / PB7(RX)
- **波特率**：115200，8N1，无流控
- **时钟源**：BUSCLK = 40MHz（IBRD=21, FBRD=45）
- **实例名**：`DL20_INST`（syscfg 生成）

---

## SysTick 定时

- Cortex-M0+ 内置 SysTick，1ms 中断
- `SysTick_Config(CPUCLK_FREQ / 1000)` → 80MHz 时每 80000 周期中断
- 全局变量 `g_tick_ms` 由 ISR 递增
- 主循环用绝对时间 `next_tick += 100` 调度，无累积漂移

---

## DIP 读取规则（⚠️ 最容易出错）

- DIP 开关一端接 GPIO，另一端接 GND
- GPIO 配置为**输入 + 内部上拉**
- **ON（闭合）= GPIO 读到 0 = 该位为 1**
- **OFF（断开）= GPIO 读到 1 = 该位为 0**

```
引脚:         PA12   PA13   PA14   PA15
DIP 位置:     第1位   第2位   第3位   第4位
ID 位:        bit0   bit1   bit2   bit3
              (LSB)                  (MSB)
值:           0x01   0x02   0x04   0x08
```

---

## ⚠️ 修改后强制同步规则

每次修改代码后必须检查：

1. **`empty.syscfg`** — 改了引脚/外设必须同步 syscfg，然后重新生成 `ti_msp_dl_config.h`
2. **`main.c` 接线注释** — 改引脚必须同步更新文件头部的接线说明
3. **[KEY_SPEC.md](KEY_SPEC.md)** — 引脚分配表、数据帧格式必须与实际代码一致

---

## 开发约定

- **不了解的 DriverLib 函数**：不要猜测 API 行为！查 TI 官方文档：
  - DriverLib API 参考手册：`https://dev.ti.com/tirex/explore/content/mspm0_sdk_2_10_00_04/docs/driverlib/mspm0_driverlib_guide/html/index.html`
  - MSPM0 SDK 总入口：`https://dev.ti.com/tirex/explore/node?node=A__AD1xb0u7P04340RmBqA31Q__MSPM0-SDK__a3PaaoK__LATEST`
- **PA18** 是 BSL 功能脚，下载/调试时该引脚不能接外设
- **UART 发送**：使用 `DL_UART_Main_transmitDataBlocking(DL20_INST, byte)`
- **GPIO 读取**：`DL_GPIO_readPins(port, pin)` 返回 0 表示低电平，非 0 表示高电平
- **时钟**：CPUCLK=80MHz，BUSCLK=40MHz，MFCLK=4MHz
