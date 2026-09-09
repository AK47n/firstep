# 03 — ir_remote_tx 模块（NEC 红外编码发射，手册 rf--Infrared-decoding-coding-module.md）

**要做什么：** 模块库新增 `ir_remote_tx` 条目（仅 mspm0）：单 GPIO 输出 38kHz NEC 载波（半周期 13us 忙等翻转 + delay 模块延时，不占 TIMER——ir_remote/ws2812 先例）——`ir_tx_init()`（空闲低）+ `ir_tx_send(address, command)`（NEC 帧：9ms/4.5ms 引导 + 地址/反码/命令/反码 4 字节 + 560us 结束位，**与批次 1 ir_remote 接收配对**：同 560us 脉宽口径 + 反码校验 + 字节内位序 MSB 先）+ `ir_tx_send_repeat()`（NEC 重复码 9ms/2.25ms）；页面是「UART 指令→红外发射」形态——UART 指令解析归生成骨架（ADR 0009），模块只出发射原语；选中后生成工程打开即可编译。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论：** 2026-09-05 完成并提交。NEC 帧参数与批次 1 ir_remote 解码阈值一对一（引导 9ms+4.5ms、位低 560us、位高 0=560us/1=1680us、重复码 2.25ms、结束位 560us——ir_remote 解码的 20us 拍窗口全部落在本发射脉宽中间）；字节内位序 MSB 先（与 ir_remote 的 value[g]<<=1 解码口径一致；标准 NEC = LSB 先，控市售设备改 `IR_TX_MSB_FIRST` 宏 = 0，notes 记录）；载波 = delay_cycles(CPUCLK_FREQ/76000) 精确换算（ws2812 先例，38kHz 半周期 13.16us）；页面「UART 指令」形态解析（帧头 A1/FA + F1/F2/F3 + 反馈）归生成骨架——框架 = UART 模块 RX 中断接收 5 字节 + 解析后调 ir_tx_send，notes 给出骨架提示；母版 syscfg 新 GPIO 实例 IR_TX（OUT 输出初始 CLEARED），默认 TX=**PA0**——与 I2C_0 SDA（ml_mpu6050 姿态）/板载 LED 重叠（红外发射链与姿态采集同选概率最低；板载 LED 随载波闪烁可作发射指示），且与 ir_remote 默认 PA26 刻意错开（发/收本就常配对——双选默认即不撞；配对时 remap 建议：两脚绑相邻排针、共地）；不占 TIMER/不注册 GPIO 中断。单选生成 → gmake 0 error / 0 warning（PASS）；未上板。**code-review 收尾修正**：ir_tx_burst 载波时长算错（每轮循环 = 一完整周期 26.3us，早产按「us/2 轮」循环 → 引导码 9ms 放大 13.16×到 118ms、位载波 560us 放大到 7.37ms——ir_remote 解码阈值窗口全面超窗、收发无法配对；修正为周期数 = us×38000/1000000）；测试增源码守卫（test_ir_remote_tx_burst_cycle_formula_guard）。

- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/rf--Infrared-decoding-coding-module.md` 「代码块」章节抽页面 bsp → 本模块只需 NEC 发射原语（页面代码是模块 5 字节串口指令 + UART 中断接收——UART 部分**不进模块**，归生成骨架）；改造为 `code/ir_remote_tx.c` + `code/ir_remote_tx.h`：`ir_tx_init` / `ir_tx_send` / `ir_tx_send_repeat`，38kHz 载波 = delay_cycles（CPUCLK_FREQ/76000）+ 电平翻转、位时序 = delay_us（560/1680/4500/2250/9000）；无 main/printf
- [x] 帧格式：引导 9ms 载波 + 4.5ms 空闲 → 4 字节（地址、~地址、命令、~命令）每字节 8 位：载波 560us + 空闲（位 1=1680us / 位 0=560us）→ 结束位 560us 载波 → 空闲低；字节内位序 MSB 先（`IR_TX_MSB_FIRST` 宏=1；与 ir_remote 解码口径一致，标准 NEC LSB 先——宏可切，notes 记录差异）；重复码 = 9ms + 2.25ms + 560us（长按节奏由调用方循环控制——ADR 0009 无状态机）
- [x] 默认脚：TX=**PA0**——与 I2C_0 SDA（ml_mpu6050 姿态）/板载 LED 重叠（红外发射链与姿态采集同选概率最低；板载 LED 随 38kHz 载波闪烁可作发射指示），**且与 ir_remote 默认 PA26 刻意错开**（发射/接收本就常配对——双选默认即不撞；同选时经引脚绑定消解）；重叠对登记 `test_pin_bindings` 刻意表（PA0 1→2 新条目）；notes 说明配对关系与 remap 建议（发/收绑相邻排针、共地供电、发射头串 100-200Ω 限流电阻 5V 供电）
- [x] 母版 `mspm0.syscfg`：新 GPIO 实例 `IR_TX`（1 associatedPin OUT，direction OUTPUT、initialValue CLEARED = 空闲低）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"IR_TX": ("ir_remote_tx",)`
- [x] `manifest.json`：`dependencies: ["delay"]`（位时序延时 + delay_cycles 载波——delay_cycles 是 ti_msp_dl_config.h 自带，delay 模块提供 delay_us）；mspm0 平台条目（files/verified 初 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接+改造要点+编译记录+页面 UART 协议说明（A1/FA + F1/F2/F3 + 反馈，归骨架）+与 ir_remote 配对关系）；pins：OUT = gpio_out（default PA0）；简介判据：能力方向（红外发射/双机红外通信/模拟家电遥控）+ 无题绑定
- [x] wordlist.json 补录：「遥控接收」加「红外编码发射头（NEC 38kHz，MCU 直驱）」方案挂 `lib_modules: ["ir_remote_tx"]`（注明与 ir_remote 配对——发射/接收常配对使用）；models 加 "红外发射头"
- [x] 测试：`test_pins.py::MSPM0_DEFAULT_MAP` 增 1 对；`test_syscfg_prune.py` 增 IR_TX 断言；`test_pin_bindings.py` 刻意表（PA0 1→2 + 注释）；新增 `tests/test_module_ir_remote_tx.py`（manifest 结构 + 单选生成 → syscfg 含 IR_TX + 文件落盘 + main.c 调 init/send 过静态门禁）
- [x] 编译验证：复制 `run_joystick_matrix.py` 改 slug 为 ir_remote_tx（main.c 调 init+send）→ gmake 真编译 0 error、模块自身 warning 0（`C:/ti/ccs2050`）；结果回写 manifest verified=true + notes 记录；code-review 后中文提交


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
