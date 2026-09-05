# 批次 1「遥控/通信」— 立创 wiki 地猛星手册模块批量入库

## 问题陈述

`lckfb-地猛星移植手册/` 的 70 篇模块移植手册已在工具里可视可预览（wiki-materials/01-02），其中 4 篇已提炼入库（ws2812/hx711/aht10/sr04，wiki-materials/03-06）。剩余 66 篇中约 58 篇**页内自带完整驱动源码**（v7 严格审计：全部调用符号页内可解 + 花括号配平无截断），但模块库里没有对应条目——用户做控制题选遥控/通信件时 AI 不知道库里有这些驱动，只能当"需自备"。

按用户裁决（本 spec 前对话）：**按控制题需要程度分批入库**；批次 1 = 遥控/通信组（hc05 蓝牙、双轴摇杆、NRF24L01、红外接收解码）——全部无需网盘。

## 方案

照 wiki-materials/03-06 已确立的管线，每件一个工单：手册代码块提炼完整驱动 → 纯驱动切片改造（去 main 演示/printf、API 规范化、时序延时走 delay 模块）→ 母版 syscfg 实例 + INSTANCE_CONSUMERS 登记 → manifest（dependencies/pins/kit/source_url/notes 含手册路径+原页+网盘链接+改造要点）→ wordlist 补录 → 生成级测试 → gmake 编译矩阵 0 error 硬门槛 → verified=true 回写 + 提交。

## 用户故事

1. 作为做题用户，我选中 `hc05`/`joystick`/`nrf24l01`/`ir_remote` 后，工具自动分配默认脚，生成工程打开即可编译，可调用 init + 服务函数。
2. 作为做题用户，我用蓝牙完成手机遥控、用摇杆做手动控制、用 NRF24L01 做双车/遥测、用红外接收解码遥控器按键，不用再读器件手册。
3. 作为维护者，查看每个新条目能看到平台条目（verified/kit/source_url/网盘链接/改造要点/编译记录），可溯源到手册。

## 实现决策

### 共性（四件一致）

- **仅 mspm0 平台条目**（stm32 缺条目 = 生成时 missing 警告，imu_uart 先例）；`hardware_bound: false`；`verified` 初始 false，编译矩阵通过转 true；未上板（真机验证留后续，按惯例 notes 注明）。
- **代码提炼**：从手册「代码块」章节抽完整 `bsp_xxx.c/h`（正文内嵌段落是行拆散版不可用），改造为：`xxx_init()` + 服务函数，去 main/printf，函数名规范化（去掉页内 `Get_`/`Set_` 菜市场命名按库风格重命名），全局状态收敛为模块内静态 + 出参指针。
- **时序**：微秒级延时全走库内 `delay` 模块（`dependencies: ["delay"]`）；**不占 TIMER 实例**（SysConfig TIMER 仅暴露 TIMG0/6/7/8/12 且已被 motor/pid/ntb_time/servo/step_motor 全占——sr04/ws2812 先例：CPU 忙等 + 时钟宏换算）。
- **引脚宏参数化**：不写死立创宏名（`GPIO_PORT`/`GPIO_XXX_PIN`），按 manifest pins 角色 + 母版 syscfg 实例宏名对齐（`<实例>_<引脚>_IOMUX` 命名，aht10 先例）。
- **默认脚**：地猛星 2×20 排针 31 个 IO 已被默认布局全占 → 新模块默认脚按「同选概率最低者与既有默认重叠」分配（IR_BEAM/PA8 与 ws2812/PA14 先例），同选经引脚绑定消解；重叠对写入 `test_pin_bindings` 刻意重叠表。
- **wordlist**：感知/通信组按条目补录（名称 + `lib_modules` 挂接），硬件词表加词条。

### 各件决策

| slug | 手册 | 外设形态 | 母版 syscfg 实例 | 关键决策 |
|---|---|---|---|---|
| `joystick` | control--two-axis-keystroke-rocker-module | 2 × 模拟（X/Y）+ 1 × 数字（SW 按键，上拉低有效） | GPIO 实例（SW）+ ADC 通道（X/Y，母版 ADC12_0 双通道先例：MEM0/MEM1） | 首选**依赖库内 `adc` 模块**读两轴（adc 模块即 MEM0/MEM1 双通道轮询；若其 pins/接口只覆盖单通道则本工单顺带扩展 adc 模块通道参数并补其测试，不新开 ADC 外设实例——MSPM0G3507 仅 ADC0 一个外设，新实例共享 ADC0 无法消解同选冲突） |
| `hc05` | rf--hc05-bluetooth-module | 1 × UART（RX 中断收发，9600；AT 模式切换 + 连接状态） | 新 UART 实例 `HC05_UART`（挂哪台外设：UART0-3 全被 IMU601/DIGIT_UART/DEBUG+UWB/ZIGBEE 占用 → 按 DIGIT/DEBUG 同 UART2 共享先例，选**同选概率最低**的外设挂靠；实现时定并注释） | 波特率 9600（HC05 模块默认；其余 UART 实例 115200——每个 UART 实例独立 targetBaudRate，无冲突）；RW 缓冲 + RX 中断解析（zigbee_uart 环形缓冲先例）；AT 模式切换函数保留为服务函数（操作模式宏） |
| `nrf24l01` | rf--nrf24l01-2-4-g-control-module | 软 SPI（CLK/MOSI/MISO/CSN/CE/IRQ，6 × GPIO） | 1 × GPIO 实例（6 associatedPins，其中 IRQ 输入中断，管脚分组 GROUP1 IIDX 分发——key/DC_MOTOR 编码器先例） | **上游缺陷记录**：页面 `#if DYNAMIC_PACKET==0` 分支引用页外 `L01_WriteSingleReg`（应为 `NRF24L01_Write_Reg`，上游残留 bug）→ 剔除该分支，notes 记录；API 保留 2.4G 收发（TX/RX payload + 地址/速率/功率配置） |
| `ir_remote`（或 `infrared_rx`，实现时定 slug） | rf--infrared-receiving-module | 1 × GPIO 输入中断（红外接收管） | 1 × GPIO 实例（输入中断，GROUP1 IIDX 分发先例） | NEC 解码脉宽（560us 级）用 **GPIO 中断 + CPU 忙等计时**（delay 模块换算），不占 TIMER（sr04 先例）；输出解码后的用户码/键值 + 重复码判定 |

### 网盘依赖（本批无）

本批四件页内源码完整（v7 审计通过）。例外项随 notes 记录、不阻塞本批：hc05/nrf24l01 的板级时序（9600 波特/SPI 时序）未上板验证。

## 测试决策

- 照 `test_module_ir_beam.py` / `test_pins.py` / `test_syscfg_prune.py` / `test_module_ws2812.py` 先例逐件：
  - `tests/test_pins.py::MSPM0_DEFAULT_MAP` 增默认脚映射（含刻意重叠对）；
  - `tests/test_syscfg_prune.py` 增新实例保留/裁剪断言；
  - 新增 `tests/test_module_<slug>.py`：manifest 结构 + 单选生成（syscfg 含实例 + 模块文件落盘 + main.c 调 init/服务函数过静态门禁）；
  - `test_pin_bindings` 刻意重叠表登记。
- 编译级验收：module-polish 编译矩阵配方 gmake 真编译（`C:/ti/ccs2050`），0 error 硬门槛、模块自身 warning 0；结果回写 manifest verified/notes。
- 每件完成后 code-review 提交；四件完成跑全量测试套件。

## 范围外

- 彩屏 6 件 + 0.96 SPI 单色（需用户从网盘下载厂家例程——批次 7，另起 spec/工单）；其余后续批次（传感器/显示/语音/环境类）另立工单。
- 已覆盖不重复：mpu6050（ml_mpu6050）、sg90（servo）、tb6612/l298n（motor）、SSD1306/SH1106 家族（oled）、灰度/循迹（huidu/xunji）。
- stm32 平台条目、上板真机验证、开新 ADC/TIMER 外设实例（冲突不可消解，本批不开）。
- 正文内嵌段落（行拆散版）不作为提炼源。

## 补充说明

- 排序依据（本 spec 前对话已确认）：`docs/next-step-options-2026-09-01.md` 决策记录——当前版本定位控制题专项，B1 按小车/控制题常用外设筛选。
- 审计脚本 `.scratch/wiki-materials/audit_v7.py` 可复跑；本批四件均在 v7 全自洽清单内。
- 工单：`issues/01-module-joystick.md` → 02 → 03 → 04（互相独立，可并行；实施按简→繁：摇杆 → hc05 → nrf24l01 → 红外接收）。
