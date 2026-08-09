# CLAUDE.md

## 项目概况

**全国大学生电子设计竞赛 — C题：基于无线通信的数字钥匙实验系统**

- 硬件平台：ALX-AOA-FIT PDOA 跟随套件（单基站 + 信标）
- 主控：STM32F103C8T6
- 核心任务：UWB 基站通过 UART 主动上报标签定位数据（距离 cm + 方位角度），STM32 解析后做区域判定与门锁控制
- **v2.0 变更**：身份识别改用 Zigbee DL-20 无线通信，UWB 只负责定位

## 当前进度（7月31日）已完成 v2.0 架构升级代码，待实测验证。

### ✅ 已完成
- 方案设计确认（见 `方案.md`）
- 套件规格书确认（见 `单基站&双基站&四基站 规格书V2.1.md`）
- 硬件采购清单确认（见 `采购.md`）
- 洞洞板焊接布局设计完成（见 `焊接布局.html`）
- **STM32 代码框架全部完成** ✅
- **代码审查完成** ✅（7月30日）
- **v2.0 架构升级** ✅（7月31日）：钥匙端+门锁端均加装 DIP-4 + Zigbee DL-20

### ✅ 已完成
- 方案设计确认（见 `方案.md`）
- 套件规格书确认（见 `单基站&双基站&四基站 规格书V2.1.md`）
- 硬件采购清单确认（见 `采购.md`）//已完成或有其他方法
- 大部分器件已购买，剩余物料待收货
- 洞洞板焊接布局设计完成（见 `焊接布局.html`）
- **STM32 代码框架全部完成** ✅
- **代码审查完成** ✅（7月30日）
  - 发现并修复 `TAGID_MASK` 未定义（编译报错）
  - 其余逻辑正确，无硬伤

### 📝 代码模块完成情况

| 模块 | 文件 | 功能 | 状态 |
|------|------|------|------|
| 引脚+参数配置 | `code/config.h` | 所有引脚映射、区域阈值、时间参数、TagID掩码 | ✅ |
| UWB帧解析 | `code/uwb_uart.c/h` | UART接收+0x2001帧解析+大端转换+XOR校验 | ✅ |
| 滑动平均滤波 | `code/filter.c/h` | 距离(窗口8)+方位角(窗口5)滑动滤波 | ✅ |
| 区域判定 | `code/zone.c/h` | 5级带滞回区域判定(10cm滞回) | ✅ |
| 锁控制+事件 | `code/lock_control.c/h` | 状态机+RGB LED+蜂鸣器+事件系统 | ✅ |
| 调试串口 | `code/debug_uart.c/h` | UART2调试输出(DEBUG_PRINTF宏) | ✅ |
| 主循环 | `user/main.c` | DIP读取→ID比对→区域判定→锁控制→OLED刷新 | ✅ |
| 中断服务 | `user/isr.c` | TIM2(1ms滴答)+USART1(UWB接收)+看门狗 | ✅ |
| 头文件汇总 | `ml_libs/headfile.h` | 精简后只保留需要的驱动+新增模块 | ✅ |

### ⚠️ 已知问题（不影响功能，有空再改）

| 问题 | 位置 | 说明 |
|------|------|------|
| buzzer_beep_ms 阻塞 | `lock_control.c:49` | 用 delay_ms() 阻塞 80ms，会短暂卡主循环 |
| blink_phase 共用 | `lock_control.c` | ID不匹配(100ms)和迎宾区(500ms)共用 blink_phase/last_toggle_tick |
| fputc 劫持 USART1 | `ml_uart.c:31` | printf 会往 USART1 发数据，跟 UWB 冲突（当前未用 printf，无害） |

### 🔜 待做（硬件到了之后）

1. 焊接硬件、接线
2. 实测 UWB 数据质量 → 微调 `config.h` 中的滤波窗口和区域阈值
3. 实测 OLED 显示效果 → 需要的话调整显示格式
4. 整机联调、测试评分项

### ⚠️ 待采购
详见 `采购.md` 待采购清单，主要包括 MP1584、HT7333、TP4056、拨码开关、端子线、杜邦线等。
- **v2.0 新增采购**：Zigbee DL-20 ×2、DIP-4 拨码开关 ×1（钥匙端）、STM32 最小系统板 ×1（钥匙端）

## UWB 套件关键认知

**信标（Tag）和基站（Anchor）都不需要编程！**

- 信标：上电即自动广播信号，内置 MCU 已烧录固件，无需任何编程
- 基站：内置 32 位 MCU，所有定位算法（TOF/PDoA/卡尔曼滤波）在模块内部完成
- 基站通过 UART 串口（115200bps）**主动上报**定位结果帧（0x2001）
- STM32 只需要：接串口 → 收字节 → 解析帧 → 提取 distance + azimuth
- 信标/基站的 ID 可通过官方配置软件修改（Windows 上位机）

## 关键文件

| 文件 | 内容 |
|------|------|
| `方案.md` | 完整技术方案（v2.0 含 Zigbee 架构） |
| `采购.md` | 采购清单、已有/待购器件、接线对照 |
| `单基站&双基站&四基站 规格书V2.1.md` | UWB 套件规格书关键参数摘要 |
| `焊接布局.html` | 洞洞板焊接布局图（浏览器打开） |
| `C题_基于无线通信的数字钥匙实验系统.docx` | 原始赛题文档 |
| `最新ALX-AOA-FIT跟随套件开发资料/` | 套件官方开发资料 |
| **门锁端代码** | |
| `code/config.h` | **引脚映射 + 全部可调参数**（含 Zigbee 引脚） |
| `code/uwb_uart.c/h` | UWB 帧解析 + 滑动滤波 |
| `code/zigbee_uart.c/h` 🆕 | **Zigbee DL-20 接收钥匙ID (USART3)** |
| `code/zone.c/h` | 区域判定（带滞回） |
| `code/lock_control.c/h` | 锁状态机 + LED + 蜂鸣器 + 事件系统 |
| `code/debug_uart.c/h` | UART2 调试串口 |
| `user/main.c` | 主循环（v2.0: Zigbee ID 比对） |
| `user/isr.c` | 中断服务（v2.0: USART3→zigbee_rx_handler） |
| **钥匙端代码** 🆕 | |
| `key_fob/config.h` | 钥匙端引脚映射 |
| `key_fob/main.c` | 钥匙端主循环（读DIP→发Zigbee→LED心跳） |
| `key_fob/zigbee_uart.c/h` | Zigbee DL-20 发送钥匙ID (UART1) |
| `key_fob/isr.c` | 钥匙端中断服务 |
| `key_fob/headfile.h` | 钥匙端头文件汇总 |

## 核心硬件架构

```
钥匙端（信标+MCU+Zigbee）：
  电池 → HT7333(3.3V) → STM32(读DIP→发Zigbee) + UWB信标(上电广播)
  
门锁端（基站+STM32+Zigbee）：
  12V电池 → MP1584(5V) → STM32 → 基站(UART1) + Zigbee(USART3) + OLED/LED/蜂鸣器
```

### 门锁端 STM32 引脚分配

| 功能 | 引脚 | 说明 |
|------|------|------|
| UWB 基站 UART | PA9(TX), PA10(RX) | UART1 @115200，基站主动上报 |
| **Zigbee DL-20** 🆕 | **PB10(TX), PB11(RX)** | **USART3 @115200，接收钥匙ID** |
| OLED | PB8(SCL), PB9(SDA) | 软件 I2C，0.96" 128×64 |
| RGB LED R | PC13 | 红灯（共阴，高电平点亮） |
| RGB LED Y | PC14 | 黄灯 |
| RGB LED G | PC15 | 绿灯 |
| 蜂鸣器 | PB0 | 有源蜂鸣器 + NPN 驱动 |
| DIP-4 拨码 | PB12, PB13, PB14, PB15 | 上拉输入，ON=低电平 |
| 调试串口 | PA2(TX), PA3(RX) | UART2 @115200，调试输出+命令接收 |

### 钥匙端 STM32 引脚分配 🆕

| 功能 | 引脚 | 说明 |
|------|------|------|
| Zigbee DL-20 | PA9(TX), PA10(RX) | UART1 @115200，发送钥匙ID |
| DIP-4 拨码 | PA0, PA1, PA2, PA3 | 上拉输入，ON=低电平 |
| 状态LED | PC13 | BluePill板载LED，心跳闪烁 |
| UWB信标 | — | 仅供电，无数据连接 |

### 区域判定参数（config.h 中调整）

| 参数 | 值 | 说明 |
|------|-----|------|
| THR_UNLOCK_ENTER | 130cm | 进入开锁区 |
| THR_UNLOCK_EXIT | 140cm | 离开开锁区 |
| THR_WELCOME_ENTER | 230cm | 进入迎宾区 |
| THR_WELCOME_EXIT | 240cm | 离开迎宾区 |
| THR_SENSING_MAX | 430cm | 最大感应距离，超出视为无钥匙 |
| FOV_HALF_ANGLE | ±45° | 有效角度范围 |
| TAG_TIMEOUT_MS | 3000ms | 超时判定钥匙离开 |
| TAGID_MASK | 0x0F | DIP-4 只比较 TagID 低4位 |

## ID 验证机制 (v2.0) 🆕

- **钥匙端**：DIP-4 → STM32 → Zigbee DL-20 → 每 100ms 发送 `[0xAA][0x55][KeyID][SUM]` (4字节, SUM=(0xAA+0x55+ID)&0xFF)
- **门锁端**：Zigbee DL-20 → USART3 → STM32 接收 → `g_key_id` vs `dip_id`
- UWB TagID **不再用于身份识别**，UWB 只负责测距/测角（定位）
- 两端 DIP-4 独立设置，只有值相同时才能开锁
- Zigbee 超时 500ms → 视为钥匙离开（钥匙端 100ms 一发，丢 5 帧判定离开）
- 钥匙端 DIP 变化 → 立即发送新ID（不等 100ms 周期）

## 通信协议关键信息

- 基站通过 UART @115200bps 主动上报
- 核心消息：0x2001（标签定位信息命令）
- 帧头：`0xFFFFFFFF`
- 帧长：37 字节（PacketLength = 0x0025）
- TagID（4B）、Distance（4B, cm）、Azimuth（2B, 度）、Elevation（2B, 度）
- XOR 校验
- 完整协议详见 `方案.md` §二

## 代码架构要点（审查记录）

- **帧解析**：union 叠加 struct 直接映射 37 字节帧，字段对齐恰好无 padding（已验证），无需 `__packed`
- **XOR 校验**：全 37 字节 XOR = 0 即正确
- **帧同步**：收到 4 个连续 0xFF 后锁定同步，逐字节收 37 字节后解析；中间出现 0xFF 不会误触发重新同步
- **滤波**：距离窗口=8，方位角窗口=5；窗口未满时用实际 count 做除数（避免前几帧被 0 拉低）
- **区域判定**：NONE → SENSING → WELCOME → UNLOCK，各级均有 10cm 滞回，FOV ±45°
- **事件系统**：单事件队列，OLED 覆盖显示 1.5 秒后恢复
- **调试输出**：`DEBUG_PRINTF` 用 sprintf + UART2，不经过 printf/USART1，与 UWB 不冲突
- **看门狗**：IWDG，LSI≈40kHz，预分频 256，重装载 625 → 约 4 秒超时

## AI 协作约定

- 我是电赛参赛选手，时间紧（4天），代码要务实、能用、不炫技
- STM32 开发环境：Keil MDK 或 STM32CubeIDE，标准库/HAL 均可
- 所有代码优先考虑可靠性和调试便利性（比如串口打印调试信息）
- 区域判定参数（阈值、滞回值、FOV 角度）用 `#define` 宏定义，方便现场调参
- 引脚映射统一在头文件顶部用 `#define`，方便改硬件
